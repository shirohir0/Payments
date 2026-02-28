from dataclasses import dataclass
from decimal import Decimal

from app.domain.money import ZERO, idempotency_key, money


@dataclass
class DepositDTO:
    user_id: int
    amount: Decimal
    commission: Decimal = ZERO
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        self.amount = money(self.amount, positive=True)
        self.commission = money(self.commission)
        self.idempotency_key = idempotency_key(self.idempotency_key)


@dataclass
class WithdrawDTO(DepositDTO):
    pass
