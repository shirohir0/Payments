from abc import ABC, abstractmethod
from domain.entities.user import User
from infrastructure.db.models.payment import PaymentModel

class IUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None:
        pass

    @abstractmethod
    async def save(self, user: User) -> None:
        pass

class IPaymentRepository(ABC):
    @abstractmethod
    async def create(self, user_id: int, amount: float, commission: float) -> PaymentModel:
        pass


class ITransactionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        user_id: int,
        payment_id: int | None,
        amount: float,
        commission: float,
        type: str,
        status: str
    ):
        pass
