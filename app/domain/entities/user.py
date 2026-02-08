from dataclasses import dataclass

from app.domain.exceptions import (
    UserInsufficientFundsError,
    UserNegativeAmountError,
    UserNegativeBalanceError,
    UserWithdrawAmountError,
)


@dataclass
class User:
    id: int | None
    balance: float

    def __post_init__(self):
        if self.balance < 0:
            raise UserNegativeBalanceError("Balance cannot be negative")

    def deposit(self, amount: float):
        if amount < 0:
            raise UserNegativeAmountError("Deposit amount must be positive")
        self.balance += amount

    def withdraw(self, amount: float):
        if amount < 0:
            raise UserWithdrawAmountError("Withdraw amount must be positive")
        if self.balance < amount:
            raise UserInsufficientFundsError("Insufficient funds")
        self.balance -= amount
