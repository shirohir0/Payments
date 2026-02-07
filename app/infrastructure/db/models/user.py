from sqlalchemy import BigInteger, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.base import Base

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    balance: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
