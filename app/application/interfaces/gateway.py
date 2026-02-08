from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID


class PaymentGateway(ABC):
    @abstractmethod
    async def charge(self, payment_id: UUID, user_id: UUID, amount: Decimal) -> None:
        raise NotImplementedError
