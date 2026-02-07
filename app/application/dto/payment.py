# application/dto/deposit_dto.py
from dataclasses import dataclass

@dataclass
class DepositDTO:
    user_id: int
    amount: float
    commission: float = 0.0  # комиссия по умолчанию
