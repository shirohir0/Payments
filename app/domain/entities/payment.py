from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums.payment_direction import PaymentDirection
from app.domain.enums.payment_status import PaymentStatus


@dataclass
class Payment:
    id: UUID
    user_id: UUID
    amount: Decimal
    direction: PaymentDirection
    status: PaymentStatus = PaymentStatus.pending
    commission: Decimal = field(default_factory=lambda: Decimal("0"))
    attempts: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
