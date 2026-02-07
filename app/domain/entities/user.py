from dataclasses import dataclass

@dataclass
class User:
    id: int | None
    balance: float

    def __post_init__(self):
        if self.balance < 0:
            raise ValueError("Balance cannot be negative")

    def deposit(self, amount: float):
        if amount < 0:
            raise ValueError("Deposit amount must be positive")
        self.balance += amount

    def withdraw(self, amount: float):
        if amount < 0:
            raise ValueError("Withdraw amount must be positive")
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        self.balance -= amount
