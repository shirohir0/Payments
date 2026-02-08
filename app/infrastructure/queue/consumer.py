import asyncio
from uuid import UUID


class PaymentQueue:
    def __init__(self, maxsize: int = 0) -> None:
        self._queue: asyncio.Queue[UUID] = asyncio.Queue(maxsize=maxsize)

    async def put(self, payment_id: UUID) -> None:
        await self._queue.put(payment_id)

    async def get(self) -> UUID:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()
