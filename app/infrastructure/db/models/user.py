from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_users_balance_nonnegative"),
        CheckConstraint("reserved_balance >= 0", name="ck_users_reserved_nonnegative"),
        CheckConstraint("reserved_balance <= balance", name="ck_users_reservation_within_balance"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default=text("0")
    )
    reserved_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00"), server_default=text("0")
    )

    @property
    def available_balance(self) -> Decimal:
        return self.balance - self.reserved_balance
