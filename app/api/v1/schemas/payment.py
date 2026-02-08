from typing import Literal, Optional

from pydantic import BaseModel, Field, PositiveFloat


class DepositRequestSchema(BaseModel):
    user_id: int = Field(..., gt=0, description="ID пользователя")
    deposit: PositiveFloat = Field(..., description="Сумма пополнения (> 0)")


class WithdrawRequestSchema(BaseModel):
    user_id: int = Field(..., gt=0, description="ID пользователя")
    amount: PositiveFloat = Field(..., description="Сумма списания (> 0)")


class PaymentCreateResponse(BaseModel):
    payment_id: int = Field(..., description="ID созданного платежа")
    user_id: int = Field(..., description="ID пользователя")
    status: Literal["processing", "success", "failed"] = Field(..., description="Текущий статус")
    deposit: Optional[float] = Field(default=None, description="Сумма пополнения, если это deposit")
    withdraw: Optional[float] = Field(default=None, description="Сумма списания, если это withdraw")


class PaymentStatusResponse(BaseModel):
    payment_id: int
    user_id: int
    amount: float
    commission: float
    status: Literal["new", "processing", "success", "failed"]
    attempts: int
    last_error: Optional[str] = None
    transaction_status: Optional[Literal["success", "failed", "processing"]] = None
