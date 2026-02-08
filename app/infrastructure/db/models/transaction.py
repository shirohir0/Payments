from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.db.base import Base

class TransactionType(PyEnum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"

class TransactionStatus(PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PROCESSING = "processing"

class TransactionModel(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    payment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    commission: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(nullable=False)

    user = relationship("UserModel", backref="transactions")
    payment = relationship("PaymentModel", backref="transactions")
