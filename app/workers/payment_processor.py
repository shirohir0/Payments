from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.metrics import metrics
from app.core.settings import settings
from app.infrastructure.db.models.payment import PaymentModel, PaymentStatus
from app.infrastructure.db.models.transaction import TransactionModel, TransactionStatus, TransactionType
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.payment_gateway.http import PaymentGatewayClient
from app.infrastructure.repositories.payment_dlq import PaymentDLQRepository

logger = logging.getLogger("payment_processor")


class PaymentProcessor:
    def __init__(self) -> None:
        self.gateway = PaymentGatewayClient()

    async def process(self, payment_id: int) -> str:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                payment = await session.get(PaymentModel, payment_id, with_for_update=True)
                if not payment:
                    logger.error("payment not found: payment_id=%s", payment_id)
                    return "not_found"

                if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
                    logger.info("payment already finalized: payment_id=%s status=%s", payment.id, payment.status.value)
                    return payment.status.value

                payment.status = PaymentStatus.PROCESSING
                payment.attempts = payment.attempts + 1
                payment.locked_at = datetime.now(timezone.utc)
                payment.next_retry_at = None
                await metrics.inc("payments_processing_started_total")

        payload = await self._build_payload(payment_id)
        if payload is None:
            await self._mark_failed(payment_id, "missing_transaction")
            return "failed"

        response = await self.gateway.charge(payload)
        if response.success:
            await metrics.inc("gateway_success_total")
            await self._apply_success(payment_id)
            return "success"

        if response.retryable:
            if response.error == "timeout":
                await metrics.inc("gateway_timeouts_total")
            else:
                await metrics.inc("gateway_errors_total")
            await self._apply_failure(payment_id, response.error or "gateway_error")
            return "retry"

        await metrics.inc("gateway_non_retryable_errors_total")
        await self._mark_failed(payment_id, response.error or "gateway_error")
        return "failed"

    async def _build_payload(self, payment_id: int) -> dict[str, object] | None:
        async with AsyncSessionLocal() as session:
            payment = await session.get(PaymentModel, payment_id)
            if not payment:
                return None

            transaction = await session.execute(
                select(TransactionModel).where(TransactionModel.payment_id == payment_id)
            )
            transaction = transaction.scalar_one_or_none()
            if not transaction:
                return None

            return {
                "payment_id": payment.id,
                "user_id": payment.user_id,
                "amount": float(payment.amount),
                "commission": float(payment.commission),
                "type": transaction.type.value,
            }

    async def _apply_success(self, payment_id: int) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                payment = await session.get(PaymentModel, payment_id, with_for_update=True)
                if not payment or payment.status == PaymentStatus.SUCCESS:
                    return

                transaction = await session.execute(
                    select(TransactionModel)
                    .where(TransactionModel.payment_id == payment_id)
                    .with_for_update()
                )
                transaction = transaction.scalar_one_or_none()
                if not transaction:
                    await self._mark_failed(payment_id, "missing_transaction")
                    return

                user = await session.get(UserModel, payment.user_id, with_for_update=True)
                if not user:
                    await self._mark_failed(payment_id, "missing_user")
                    transaction.status = TransactionStatus.FAILED
                    return

                if transaction.type == TransactionType.DEPOSIT:
                    net_amount = float(payment.amount) - float(payment.commission)
                    user.balance = float(user.balance) + net_amount
                else:
                    total_amount = float(payment.amount) + float(payment.commission)
                    if float(user.balance) < total_amount:
                        await self._mark_failed(payment_id, "insufficient_funds")
                        transaction.status = TransactionStatus.FAILED
                        return
                    user.balance = float(user.balance) - total_amount

                payment.status = PaymentStatus.SUCCESS
                payment.last_error = None
                payment.locked_at = None
                payment.next_retry_at = None
                transaction.status = TransactionStatus.SUCCESS

                await metrics.inc("payments_success_total")
                logger.info("payment success: payment_id=%s", payment.id)

    async def _apply_failure(self, payment_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                payment = await session.get(PaymentModel, payment_id, with_for_update=True)
                if not payment:
                    return

                if payment.attempts >= settings.gateway_max_attempts:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = error
                    payment.locked_at = None
                    await metrics.inc("payments_failed_total")
                    await self._write_dlq(session, payment, error)
                    logger.error("payment failed: max_attempts payment_id=%s", payment.id)
                    return

                await metrics.inc("payments_retried_total")
                backoff_seconds = settings.gateway_backoff_base_seconds * (2 ** (payment.attempts - 1))
                backoff_seconds = min(backoff_seconds, settings.gateway_backoff_max_seconds)
                jitter = random.uniform(0, settings.gateway_backoff_jitter_seconds)
                payment.status = PaymentStatus.NEW
                payment.last_error = error
                payment.locked_at = None
                payment.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds + jitter)

    async def _mark_failed(self, payment_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                payment = await session.get(PaymentModel, payment_id, with_for_update=True)
                if not payment:
                    return

                payment.status = PaymentStatus.FAILED
                payment.last_error = error
                payment.locked_at = None
                await metrics.inc("payments_failed_total")
                await self._write_dlq(session, payment, error)
                logger.error("payment failed: payment_id=%s error=%s", payment.id, error)

    async def _write_dlq(self, session, payment: PaymentModel, error: str) -> None:
        repo = PaymentDLQRepository(session)
        existing = await repo.get_by_payment_id(payment.id)
        if existing:
            return

        transaction = await session.execute(
            select(TransactionModel).where(TransactionModel.payment_id == payment.id)
        )
        transaction = transaction.scalar_one_or_none()
        payment_type = transaction.type.value if transaction else "unknown"

        await repo.create(
            payment_id=payment.id,
            user_id=payment.user_id,
            amount=float(payment.amount),
            commission=float(payment.commission),
            payment_type=payment_type,
            error=error,
            attempts=payment.attempts,
        )
        await metrics.inc("dlq_written_total")
        logger.warning("dlq written: payment_id=%s error=%s", payment.id, error)
