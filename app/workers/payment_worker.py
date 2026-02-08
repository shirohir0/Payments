import asyncio
import logging
from typing import Awaitable, Callable
from uuid import UUID

from app.infrastructure.queue.consumer import PaymentQueue

logger = logging.getLogger(__name__)


class PaymentWorker:
    def __init__(self, queue: PaymentQueue, handler: Callable[[UUID], Awaitable[None]]) -> None:
        self._queue = queue
        self._handler = handler
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="payment-worker")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info("Payment worker stopped")

    async def _run(self) -> None:
        while self._running:
            payment_id = await self._queue.get()
            try:
                await self._handler(payment_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Payment processing failed", extra={"payment_id": payment_id, "error": str(exc)})
            finally:
                self._queue.task_done()
