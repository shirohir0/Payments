from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.payment import NonnegativeMoney


class CreateUserSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    balance: NonnegativeMoney = Field(description="Initial balance")


class UserResponseSchema(BaseModel):
    id: int
    balance: Decimal
    reserved_balance: Decimal = Decimal("0.00")
