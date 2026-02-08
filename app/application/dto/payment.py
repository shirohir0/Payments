from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums.payment_direction import PaymentDirection
from app.domain.enums.payment_status import PaymentStatus


class PaymentCreateRequest(BaseModel):
    user_id: UUID
    amount: Decimal = Field(gt=0)
    direction: PaymentDirection


class PaymentResponse(BaseModel):
    id: UUID
    user_id: UUID
    amount: Decimal
    direction: PaymentDirection
    status: PaymentStatus
    commission: Decimal


class PaymentStatusResponse(BaseModel):
    id: UUID
    status: PaymentStatus
    attempts: int
    commission: Decimal
