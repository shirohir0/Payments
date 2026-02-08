import asyncio
from typing import Dict
from uuid import UUID

from app.application.interfaces.repositories import PaymentRepository
from app.domain.entities.payment import Payment


class InMemoryPaymentRepository(PaymentRepository):
    def __init__(self) -> None:
        self._items: Dict[UUID, Payment] = {}
        self._lock = asyncio.Lock()

    async def create(self, payment: Payment) -> None:
        async with self._lock:
            self._items[payment.id] = payment

    async def get(self, payment_id: UUID) -> Payment | None:
        async with self._lock:
            return self._items.get(payment_id)

    async def update(self, payment: Payment) -> None:
        async with self._lock:
            self._items[payment.id] = payment
