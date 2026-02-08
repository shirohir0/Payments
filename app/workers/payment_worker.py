from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import metrics
from app.core.settings import settings
from app.infrastructure.db.models.payment import PaymentModel, PaymentStatus
from app.infrastructure.db.models.payment_task import PaymentTaskModel, PaymentTaskStatus
from app.infrastructure.db.models.transaction import TransactionModel, TransactionStatus, TransactionType
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.payment_gateway.http import PaymentGatewayClient
from app.infrastructure.repositories.payment_dlq import PaymentDLQRepository
from app.infrastructure.repositories.payment_task import PaymentTaskRepository

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
            task_id = await self._reserve_task()
            if task_id is None:
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue

            await self._process_task(task_id)

        logger.info("payment worker stopped")

    async def _reserve_task(self) -> int | None:
        now = datetime.now(timezone.utc)
        stuck_before = now - timedelta(seconds=settings.worker_processing_timeout_seconds)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                repo = PaymentTaskRepository(session)
                task = await repo.reserve_next(now=now, stuck_before=stuck_before)
                if not task:
                    return None

                task.status = PaymentTaskStatus.PROCESSING
                task.attempts = task.attempts + 1
                task.locked_at = now
                task.next_retry_at = None

                payment = await session.get(PaymentModel, task.payment_id, with_for_update=True)
                if payment:
                    if payment.status == PaymentStatus.SUCCESS:
                        task.status = PaymentTaskStatus.DONE
                        task.locked_at = None
                        return None
                    if payment.status == PaymentStatus.FAILED:
                        task.status = PaymentTaskStatus.FAILED
                        task.last_error = payment.last_error
                        task.locked_at = None
                        return None

                    payment.status = PaymentStatus.PROCESSING
                    payment.attempts = task.attempts
                    payment.locked_at = now
                    payment.next_retry_at = None
                await session.flush()
                await metrics.inc("payments_processing_started_total")

                return task.id

    async def _process_task(self, task_id: int) -> None:
        payload = await self._build_payload_from_task(task_id)
        if payload is None:
            await self._mark_failed_task(task_id, "missing_transaction")
            return

        response = await self.gateway.charge(payload)
        if response.success:
            await metrics.inc("gateway_success_total")
            await self._apply_success(task_id)
            return

        if response.retryable:
            if response.error == "timeout":
                await metrics.inc("gateway_timeouts_total")
            else:
                await metrics.inc("gateway_errors_total")
            await self._apply_failure(task_id, response.error or "gateway_error")
        else:
            await metrics.inc("gateway_non_retryable_errors_total")
            await self._mark_failed_task(task_id, response.error or "gateway_error")

    async def _build_payload_from_task(self, task_id: int) -> dict[str, object] | None:
        async with AsyncSessionLocal() as session:
            task = await session.get(PaymentTaskModel, task_id)
            if not task:
                return None

            payment = await session.get(PaymentModel, task.payment_id)
            if not payment:
                return None

            transaction = await session.execute(
                select(TransactionModel).where(TransactionModel.payment_id == payment.id)
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

    async def _apply_success(self, task_id: int) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = await session.get(PaymentTaskModel, task_id, with_for_update=True)
                if not task:
                    return

                payment = await session.get(PaymentModel, task.payment_id, with_for_update=True)
                if not payment or payment.status == PaymentStatus.SUCCESS:
                    task.status = PaymentTaskStatus.DONE
                    task.locked_at = None
                    return

                transaction = await session.execute(
                    select(TransactionModel)
                    .where(TransactionModel.payment_id == payment.id)
                    .with_for_update()
                )
                transaction = transaction.scalar_one_or_none()
                if not transaction:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = "missing_transaction"
                    payment.locked_at = None
                    task.status = PaymentTaskStatus.FAILED
                    task.last_error = "missing_transaction"
                    task.locked_at = None
                    await metrics.inc("payments_failed_total")
                    await self._write_dlq(session, payment, transaction, "missing_transaction")
                    return

                user = await session.get(UserModel, payment.user_id, with_for_update=True)
                if not user:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = "missing_user"
                    payment.locked_at = None
                    transaction.status = TransactionStatus.FAILED
                    task.status = PaymentTaskStatus.FAILED
                    task.last_error = "missing_user"
                    task.locked_at = None
                    await metrics.inc("payments_failed_total")
                    await self._write_dlq(session, payment, transaction, "missing_user")
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
                        task.status = PaymentTaskStatus.FAILED
                        task.last_error = "insufficient_funds"
                        task.locked_at = None
                        await metrics.inc("payments_failed_total")
                        await self._write_dlq(session, payment, transaction, "insufficient_funds")
                        return
                    user.balance = float(user.balance) - total_amount

                payment.status = PaymentStatus.SUCCESS
                payment.last_error = None
                payment.locked_at = None
                payment.next_retry_at = None
                transaction.status = TransactionStatus.SUCCESS

                task.status = PaymentTaskStatus.DONE
                task.last_error = None
                task.locked_at = None
                task.next_retry_at = None

                await metrics.inc("payments_success_total")

    async def _apply_failure(self, task_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = await session.get(PaymentTaskModel, task_id, with_for_update=True)
                if not task:
                    return

                payment = await session.get(PaymentModel, task.payment_id, with_for_update=True)
                if not payment:
                    task.status = PaymentTaskStatus.FAILED
                    task.last_error = "missing_payment"
                    task.locked_at = None
                    return
                payment.attempts = task.attempts

                transaction = await session.execute(
                    select(TransactionModel)
                    .where(TransactionModel.payment_id == payment.id)
                    .with_for_update()
                )
                transaction = transaction.scalar_one_or_none()

                if task.attempts >= settings.gateway_max_attempts:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = error
                    payment.locked_at = None
                    if transaction:
                        transaction.status = TransactionStatus.FAILED
                    task.status = PaymentTaskStatus.FAILED
                    task.last_error = error
                    task.locked_at = None
                    await metrics.inc("payments_failed_total")
                    await self._write_dlq(session, payment, transaction, error)
                    return

                await metrics.inc("payments_retried_total")
                backoff_seconds = settings.gateway_backoff_base_seconds * (2 ** (task.attempts - 1))
                backoff_seconds = min(backoff_seconds, settings.gateway_backoff_max_seconds)
                jitter = random.uniform(0, settings.gateway_backoff_jitter_seconds)
                task.status = PaymentTaskStatus.NEW
                task.last_error = error
                task.locked_at = None
                task.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds + jitter)
                if transaction:
                    transaction.status = TransactionStatus.PROCESSING

                payment.status = PaymentStatus.NEW
                payment.last_error = error
                payment.locked_at = None
                payment.next_retry_at = task.next_retry_at
                payment.attempts = task.attempts

    async def _mark_failed_task(self, task_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                task = await session.get(PaymentTaskModel, task_id, with_for_update=True)
                if not task:
                    return
                task.status = PaymentTaskStatus.FAILED
                task.last_error = error
                task.locked_at = None

                payment = await session.get(PaymentModel, task.payment_id, with_for_update=True)
                if payment:
                    payment.status = PaymentStatus.FAILED
                    payment.last_error = error
                    payment.locked_at = None
                    payment.attempts = task.attempts

                transaction = await session.execute(
                    select(TransactionModel)
                    .where(TransactionModel.payment_id == task.payment_id)
                    .with_for_update()
                )
                transaction = transaction.scalar_one_or_none()
                if transaction:
                    transaction.status = TransactionStatus.FAILED

                await metrics.inc("payments_failed_total")
                if payment:
                    await self._write_dlq(session, payment, transaction, error)

    async def _write_dlq(
        self,
        session: AsyncSession,
        payment: PaymentModel,
        transaction: TransactionModel | None,
        error: str,
    ) -> None:
        repo = PaymentDLQRepository(session)
        existing = await repo.get_by_payment_id(payment.id)
        if existing:
            return

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
