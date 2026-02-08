from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID


@dataclass
class User:
    id: UUID
    balance: Decimal = field(default_factory=lambda: Decimal("0"))
