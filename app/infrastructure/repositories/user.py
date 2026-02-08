import asyncio
from decimal import Decimal
from typing import Dict
from uuid import UUID

from app.application.interfaces.repositories import UserRepository
from app.domain.entities.user import User


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._items: Dict[UUID, User] = {}
        self._lock = asyncio.Lock()

    async def create(self, user: User) -> None:
        async with self._lock:
            self._items[user.id] = user

    async def get(self, user_id: UUID) -> User | None:
        async with self._lock:
            return self._items.get(user_id)

    async def update(self, user: User) -> None:
        async with self._lock:
            self._items[user.id] = user

    async def seed(self, user_id: UUID, balance: Decimal) -> User:
        user = User(id=user_id, balance=balance)
        await self.create(user)
        return user
