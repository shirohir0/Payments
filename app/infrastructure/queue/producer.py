from uuid import UUID

from app.infrastructure.queue.consumer import PaymentQueue


class PaymentQueueProducer:
    def __init__(self, queue: PaymentQueue) -> None:
        self._queue = queue

    async def enqueue(self, payment_id: UUID) -> None:
        await self._queue.put(payment_id)
