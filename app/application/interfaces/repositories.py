from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain.entities.user import User
from app.infrastructure.db.models.payment import PaymentModel
from app.infrastructure.db.models.user import UserModel


class IUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None:
        pass

    @abstractmethod
    async def get_for_update(self, user_id: int) -> UserModel | None:
        pass

    @abstractmethod
    async def save(self, user: User) -> None:
        pass


class IPaymentRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: int,
        amount: Decimal,
        commission: Decimal,
        *,
        operation: str,
    ) -> PaymentModel:
        pass


class ITransactionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: int,
        payment_id: int | None,
        amount: Decimal,
        commission: Decimal,
        type: str,
        status: str,
    ):
        pass
