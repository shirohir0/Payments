# api/v1/schemas/payment.py
from pydantic import BaseModel, Field, PositiveFloat

class DepositRequestSchema(BaseModel):
    user_id: int = Field(..., gt=0)
    deposit: PositiveFloat  # автоматически проверяет > 0
class WithdrawRequestSchema(BaseModel):
    user_id: int = Field(..., gt=0)
    amount: PositiveFloat
