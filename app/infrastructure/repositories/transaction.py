import asyncio
from typing import Dict, List
from uuid import UUID

from app.application.interfaces.repositories import TransactionRepository
from app.domain.entities.transaction import Transaction


class InMemoryTransactionRepository(TransactionRepository):
    def __init__(self) -> None:
        self._items: Dict[UUID, List[Transaction]] = {}
        self._lock = asyncio.Lock()

    async def add(self, transaction: Transaction) -> None:
        async with self._lock:
            self._items.setdefault(transaction.payment_id, []).append(transaction)

    async def list_by_payment(self, payment_id: UUID) -> list[Transaction]:
        async with self._lock:
            return list(self._items.get(payment_id, []))
