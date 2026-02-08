from abc import ABC, abstractmethod
from typing import Iterable
from uuid import UUID

from app.domain.entities.payment import Payment
from app.domain.entities.transaction import Transaction
from app.domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    async def create(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, user_id: UUID) -> User:
        raise NotImplementedError

    @abstractmethod
    async def update(self, user: User) -> None:
        raise NotImplementedError


class PaymentRepository(ABC):
    @abstractmethod
    async def create(self, payment: Payment) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, payment_id: UUID) -> Payment:
        raise NotImplementedError

    @abstractmethod
    async def update(self, payment: Payment) -> None:
        raise NotImplementedError


class TransactionRepository(ABC):
    @abstractmethod
    async def add(self, transaction: Transaction) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_payment(self, payment_id: UUID) -> Iterable[Transaction]:
        raise NotImplementedError
