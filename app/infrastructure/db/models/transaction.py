from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, Numeric, UniqueConstraint
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
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_transactions_payment_id"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("commission >= 0", name="ck_transactions_commission_nonnegative"),
        Index("ix_transactions_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transactiontype",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(
            TransactionStatus,
            name="transactionstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    user = relationship("UserModel", backref="transactions")
    payment = relationship("PaymentModel", backref="transactions")
