from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.transaction import (
    TransactionModel,
    TransactionStatus,
    TransactionType,
)


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        payment_id: int | None,
        amount: Decimal,
        commission: Decimal,
        type: str,
        status: str,
    ) -> TransactionModel:
        transaction = TransactionModel(
            user_id=user_id,
            payment_id=payment_id,
            amount=amount,
            commission=commission,
            type=TransactionType(type),
            status=TransactionStatus(status),
        )
        self.session.add(transaction)
        return transaction

    async def get_by_payment_id(self, payment_id: int) -> TransactionModel | None:
        result = await self.session.execute(
            select(TransactionModel).where(TransactionModel.payment_id == payment_id)
        )
        return result.scalar_one_or_none()
