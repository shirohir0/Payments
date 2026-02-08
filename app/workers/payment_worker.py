from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.infrastructure.db.models.payment import PaymentModel, PaymentStatus
from app.infrastructure.db.models.transaction import TransactionModel, TransactionStatus, TransactionType
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.payment_gateway.http import PaymentGatewayClient

logger = logging.getLogger("payment_worker")


class PaymentWorker:
    def __init__(self):
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self.gateway = PaymentGatewayClient()

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            await self._task

    async def run(self) -> None:
        logger.info("payment worker started")
        while not self._stop_event.is_set():
            payment_id = await self._reserve_payment()
            if payment_id is None:
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue

            await self._process_payment(payment_id)

        logger.info("payment worker stopped")

    async def _reserve_payment(self) -> int | None:
        now = datetime.now(timezone.utc)
        stuck_before = now - timedelta(seconds=settings.worker_processing_timeout_seconds)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = (
                    select(PaymentModel)
                    .where(
                        or_(
                            PaymentModel.status == PaymentStatus.NEW,
                            and_(
                                PaymentModel.status == PaymentStatus.PROCESSING,
                                PaymentModel.locked_at.is_not(None),
                                PaymentModel.locked_at < stuck_before,
                            ),
                        )
                    )
                    .where(
                        or_(
                            PaymentModel.next_retry_at.is_(None),
                            PaymentModel.next_retry_at <= now,
                        )
                    )
                    .order_by(PaymentModel.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )

                result = await session.execute(stmt)
                payment = result.scalar_one_or_none()
                if not payment:
                    return None

                payment.status = PaymentStatus.PROCESSING
                payment.attempts = payment.attempts + 1
                payment.locked_at = now
                payment.next_retry_at = None
                await session.flush()

                return payment.id

    async def _process_payment(self, payment_id: int) -> None:
        payload = await self._build_payload(payment_id)
        if payload is None:
            await self._mark_failed(payment_id, "missing_transaction")
            return

        response = await self.gateway.charge(payload)
        if response.success:
            await self._apply_success(payment_id)
            return

        if response.retryable:
            await self._apply_failure(payment_id, response.error or "gateway_error")
        else:
            await self._mark_failed(payment_id, response.error or "gateway_error")

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
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = "missing_transaction"
                    payment.locked_at = None
                    return

                user = await session.get(UserModel, payment.user_id, with_for_update=True)
                if not user:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = "missing_user"
                    payment.locked_at = None
                    transaction.status = TransactionStatus.FAILED
                    return

                if transaction.type == TransactionType.DEPOSIT:
                    net_amount = float(payment.amount) - float(payment.commission)
                    user.balance = float(user.balance) + net_amount
                else:
                    total_amount = float(payment.amount) + float(payment.commission)
                    if float(user.balance) < total_amount:
                        payment.status = PaymentStatus.FAILED
                        payment.last_error = "insufficient_funds"
                        payment.locked_at = None
                        transaction.status = TransactionStatus.FAILED
                        return
                    user.balance = float(user.balance) - total_amount

                payment.status = PaymentStatus.SUCCESS
                payment.last_error = None
                payment.locked_at = None
                payment.next_retry_at = None
                transaction.status = TransactionStatus.SUCCESS

    async def _apply_failure(self, payment_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                payment = await session.get(PaymentModel, payment_id, with_for_update=True)
                if not payment:
                    return

                transaction = await session.execute(
                    select(TransactionModel)
                    .where(TransactionModel.payment_id == payment_id)
                    .with_for_update()
                )
                transaction = transaction.scalar_one_or_none()

                if payment.attempts >= settings.gateway_max_attempts:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = error
                    payment.locked_at = None
                    if transaction:
                        transaction.status = TransactionStatus.FAILED
                    return

                backoff_seconds = settings.gateway_backoff_base_seconds * (2 ** (payment.attempts - 1))
                backoff_seconds = min(backoff_seconds, settings.gateway_backoff_max_seconds)
                jitter = random.uniform(0, settings.gateway_backoff_jitter_seconds)
                payment.status = PaymentStatus.NEW
                payment.last_error = error
                payment.locked_at = None
                payment.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds + jitter)
                if transaction:
                    transaction.status = TransactionStatus.PROCESSING

    async def _mark_failed(self, payment_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                payment = await session.get(PaymentModel, payment_id, with_for_update=True)
                if not payment:
                    return
                payment.status = PaymentStatus.FAILED
                payment.last_error = error
                payment.locked_at = None

                transaction = await session.execute(
                    select(TransactionModel)
                    .where(TransactionModel.payment_id == payment_id)
                    .with_for_update()
                )
                transaction = transaction.scalar_one_or_none()
                if transaction:
                    transaction.status = TransactionStatus.FAILED
