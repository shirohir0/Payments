from dataclasses import dataclass
from decimal import Decimal

from app.domain.exceptions import UserInsufficientFundsError, UserNegativeBalanceError
from app.domain.money import ZERO, money


@dataclass
class User:
    id: int | None
    balance: Decimal
    reserved_balance: Decimal = ZERO

    def __post_init__(self) -> None:
        self.balance = money(self.balance)
        self.reserved_balance = money(self.reserved_balance)
        if self.reserved_balance > self.balance:
            raise UserNegativeBalanceError("Reserved balance cannot exceed total balance")

    @property
    def available_balance(self) -> Decimal:
        return self.balance - self.reserved_balance

    def deposit(self, amount: Decimal) -> None:
        self.balance = money(self.balance + money(amount, positive=True))

    def withdraw(self, amount: Decimal) -> None:
        amount = money(amount, positive=True)
        if self.available_balance < amount:
            raise UserInsufficientFundsError("Insufficient available funds")
        self.balance -= amount
