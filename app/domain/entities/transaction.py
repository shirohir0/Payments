from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class Transaction:
    id: UUID
    payment_id: UUID
    user_id: UUID
    amount: Decimal
    category: str
    created_at: datetime = field(default_factory=datetime.utcnow)
