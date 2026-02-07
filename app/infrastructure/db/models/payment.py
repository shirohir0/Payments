# infrastructure/db/models/payment.py
from enum import Enum as PyEnum

from sqlalchemy import (
    ForeignKey,
    Numeric,
    Enum,
)
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base

class PaymentStatus(PyEnum):
    NEW = "new"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    commission: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.NEW,
        nullable=False,
    )
