from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.domain.money import money

PositiveMoney = Annotated[
    Decimal,
    BeforeValidator(lambda value: money(value, positive=True)),
    Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False),
]
NonnegativeMoney = Annotated[
    Decimal,
    BeforeValidator(money),
    Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False),
]


class DepositRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0, description="User ID")
    deposit: PositiveMoney = Field(description="Deposit amount; at most two decimal places")


class WithdrawRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0, description="User ID")
    amount: PositiveMoney = Field(description="Withdrawal amount; at most two decimal places")


class PaymentCreateResponse(BaseModel):
    payment_id: int
    user_id: int
    status: Literal["new", "processing", "success", "failed"]
    deposit: Decimal | None = None
    withdraw: Decimal | None = None


class PaymentStatusResponse(BaseModel):
    payment_id: int
    user_id: int
    amount: Decimal
    commission: Decimal
    status: Literal["new", "processing", "success", "failed"]
    attempts: int
    last_error: str | None = None
    transaction_status: Literal["success", "failed", "processing"] | None = None
