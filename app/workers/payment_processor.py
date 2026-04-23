"""Fenced payment processing; external calls never hold database locks."""

import logging
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.core.metrics import metrics
from app.core.settings import settings
from app.infrastructure.db.models.outbox import OutboxEvent, PaymentResolution
from app.infrastructure.db.models.payment import PaymentModel, PaymentStatus
from app.infrastructure.db.models.payment_dlq import PaymentDLQModel
from app.infrastructure.db.models.transaction import TransactionModel, TransactionStatus
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.payment_gateway.http import GatewayResponse, PaymentGatewayClient

logger = logging.getLogger("payment_processor")


def utcnow() -> datetime:
    return datetime.now(UTC)


def retry_delay(attempt: int) -> float:
    base = settings.gateway_backoff_base_seconds * (2 ** max(0, attempt - 1))
    return min(base, settings.gateway_backoff_max_seconds) + random.uniform(
        0, settings.gateway_backoff_jitter_seconds
    )


class PaymentProcessor:
    def __init__(self, *, session_factory=None, gateway=None) -> None:
        self.sessions = session_factory or AsyncSessionLocal
        self.gateway = gateway or PaymentGatewayClient()

    async def process(self, payment_id: int) -> str:
        claim = await self._claim(payment_id)
        if isinstance(claim, str):
            return claim
        token, payload = claim
        response = await self.gateway.charge(payload)
        return await self._finish(payment_id, token, response)

    async def _claim(self, payment_id: int):
        now = utcnow()
        async with self.sessions() as session, session.begin():
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.payment_id == payment_id).with_for_update()
            )
            if event is None:
                return "not_found"
            payment = await session.get(PaymentModel, payment_id, with_for_update=True)
            if payment is None:
                return "not_found"
            if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
                event.completed_at = event.completed_at or now
                return payment.status.value
            if event.completed_at is not None:
                return "reconciliation"
            if event.lease_until is not None and event.lease_until > now:
                return "busy"
            if event.lease_token is not None and payment.status == PaymentStatus.PROCESSING:
                # A previous process may have charged successfully and died
                # before recording its result. Reclaiming its lease cannot
                # establish that no external side effect happened.
                event.outcome_uncertain = True
            if payment.next_retry_at is not None and payment.next_retry_at > now:
                event.available_at = payment.next_retry_at
                return "deferred"
            if payment.attempts >= settings.gateway_max_attempts:
                self._reconciliation(payment, event, "abandoned_attempt_limit", now)
                return "reconciliation"
            transaction = await session.scalar(
                select(TransactionModel).where(TransactionModel.payment_id == payment_id)
            )
            if transaction is None:
                self._reconciliation(payment, event, "missing_transaction", now)
                return "reconciliation"
            if payment.operation == "withdraw" and not payment.funds_reserved:
                self._reconciliation(payment, event, "missing_reservation", now)
                return "reconciliation"
            token = str(uuid4())
            event.lease_token = token
            event.lease_until = now + timedelta(seconds=settings.worker_processing_timeout_seconds)
            event.available_at = event.lease_until
            event.relay_token = None
            event.relay_lease_until = None
            payment.status = PaymentStatus.PROCESSING
            payment.attempts += 1
            payment.locked_at = now
            payment.next_retry_at = None
            payload = {
                "payment_id": payment.id,
                "user_id": payment.user_id,
                "amount": str(payment.amount),
                "commission": str(payment.commission),
                "type": payment.operation,
            }
        await metrics.inc("payments_processing_started_total")
        return token, payload

    async def _finish(self, payment_id: int, token: str, result: GatewayResponse) -> str:
        now = utcnow()
        async with self.sessions() as session, session.begin():
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.payment_id == payment_id).with_for_update()
            )
            if event is None or event.lease_token != token or event.completed_at is not None:
                return "superseded"
            payment = await session.get(PaymentModel, payment_id, with_for_update=True)
            if payment is None:
                return "not_found"
            if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
                return payment.status.value
            transaction = await session.scalar(
                select(TransactionModel)
                .where(TransactionModel.payment_id == payment_id)
                .with_for_update()
            )
            user = await session.get(UserModel, payment.user_id, with_for_update=True)
            if user is None or transaction is None:
                self._reconciliation(payment, event, "missing_account_or_transaction", now)
                return "reconciliation"
            event.outcome_uncertain = event.outcome_uncertain or result.uncertain
            if result.success:
                state = await self._settle(payment, transaction, user, event, now)
                await metrics.inc("gateway_success_total")
                return state
            error = result.error or "gateway_error"
            if result.retryable and payment.attempts < settings.gateway_max_attempts:
                due = now + timedelta(seconds=retry_delay(payment.attempts))
                payment.status = PaymentStatus.NEW
                payment.next_retry_at = due
                payment.last_error = error
                payment.locked_at = None
                event.available_at = due
                event.last_error = error
                event.lease_token = None
                event.lease_until = None
                await metrics.inc("payments_retried_total")
                return "retry"
            if event.outcome_uncertain:
                self._reconciliation(payment, event, error, now)
                await metrics.inc("payments_reconciliation_total")
                return "reconciliation"
            return await self._decline(session, payment, transaction, user, event, error, now)

    @staticmethod
    def _reconciliation(payment, event, error: str, now: datetime) -> None:
        payment.status = PaymentStatus.PROCESSING
        payment.last_error = f"reconciliation_required:{error}"[:500]
        payment.locked_at = None
        payment.next_retry_at = None
        event.last_error = payment.last_error
        event.completed_at = now
        event.lease_token = None
        event.lease_until = None
        event.relay_token = None
        event.relay_lease_until = None
        logger.error("payment requires reconciliation payment_id=%s reason=%s", payment.id, error)

    async def _settle(self, payment, transaction, user, event, now) -> str:
        amount, commission = Decimal(payment.amount), Decimal(payment.commission)
        if payment.operation == "withdraw":
            total = amount + commission
            if not payment.funds_reserved or user.reserved_balance < total or user.balance < total:
                self._reconciliation(
                    payment, event, "invalid_reservation_after_provider_success", now
                )
                return "reconciliation"
            user.balance -= total
            user.reserved_balance -= total
            payment.funds_reserved = False
        else:
            new_balance = user.balance + amount - commission
            if new_balance > Decimal("9999999999.99"):
                self._reconciliation(payment, event, "balance_limit_after_provider_success", now)
                return "reconciliation"
            user.balance = new_balance
        payment.status = PaymentStatus.SUCCESS
        transaction.status = TransactionStatus.SUCCESS
        payment.last_error = None
        payment.locked_at = None
        payment.next_retry_at = None
        self._complete(event, now)
        await metrics.inc("payments_success_total")
        logger.info("payment settled payment_id=%s", payment.id)
        return "success"

    async def _decline(self, session, payment, transaction, user, event, error, now) -> str:
        if payment.funds_reserved:
            total = Decimal(payment.amount) + Decimal(payment.commission)
            if user.reserved_balance < total:
                self._reconciliation(payment, event, "invalid_reservation_on_decline", now)
                return "reconciliation"
            user.reserved_balance -= total
            payment.funds_reserved = False
        payment.status = PaymentStatus.FAILED
        payment.last_error = error[:500]
        payment.locked_at = None
        payment.next_retry_at = None
        transaction.status = TransactionStatus.FAILED
        self._complete(event, now)
        existing = await session.scalar(
            select(PaymentDLQModel).where(PaymentDLQModel.payment_id == payment.id)
        )
        if existing is None:
            session.add(
                PaymentDLQModel(
                    payment_id=payment.id,
                    user_id=payment.user_id,
                    amount=payment.amount,
                    commission=payment.commission,
                    payment_type=payment.operation,
                    error=error[:500],
                    attempts=payment.attempts,
                )
            )
        await metrics.inc("payments_failed_total")
        return "failed"

    @staticmethod
    def _complete(event, now) -> None:
        event.completed_at = now
        event.last_error = None
        event.lease_token = None
        event.lease_until = None
        event.relay_token = None
        event.relay_lease_until = None

    async def resolve(self, payment_id: int, outcome: str, reference: str) -> str:
        """Record an operator-verified provider result without charging again."""
        if outcome not in ("success", "failed"):
            raise ValueError("Outcome must be success or failed")
        if not reference.strip() or len(reference) > 200:
            raise ValueError("A provider verification reference of 1..200 characters is required")
        now = utcnow()
        async with self.sessions() as session, session.begin():
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.payment_id == payment_id).with_for_update()
            )
            payment = await session.get(PaymentModel, payment_id, with_for_update=True)
            if event is None or payment is None:
                raise ValueError("Payment not found")
            if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
                raise ValueError("Payment is already finalized")
            if event.completed_at is None or not (event.last_error or "").startswith(
                "reconciliation_required:"
            ):
                raise ValueError("Payment is not awaiting manual reconciliation")
            if (event.last_error or "").startswith("reconciliation_required:legacy_"):
                raise ValueError(
                    "Legacy payment needs accounting repair before automated resolution"
                )
            transaction = await session.scalar(
                select(TransactionModel)
                .where(TransactionModel.payment_id == payment_id)
                .with_for_update()
            )
            user = await session.get(UserModel, payment.user_id, with_for_update=True)
            if user is None or transaction is None:
                raise ValueError("Account or transaction missing; database repair required")
            if outcome == "success":
                state = await self._settle(payment, transaction, user, event, now)
            else:
                state = await self._decline(
                    session, payment, transaction, user, event, "provider_declined", now
                )
            if state != outcome:
                raise ValueError("Accounting invariant failed; database repair required")
            session.add(
                PaymentResolution(
                    payment_id=payment_id, outcome=outcome, reference=reference.strip()
                )
            )
            logger.warning("operator resolution payment_id=%s outcome=%s", payment_id, state)
            return state
