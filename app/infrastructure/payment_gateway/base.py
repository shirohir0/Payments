from abc import ABC, abstractmethod


class PaymentGatewayClient(ABC):
    @abstractmethod
    async def charge(self, payment_id: int, user_id: int, amount: float) -> None:
        raise NotImplementedError
