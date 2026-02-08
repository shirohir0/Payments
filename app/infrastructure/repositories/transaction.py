from infrastructure.db.models.transaction import TransactionModel, TransactionType, TransactionStatus
from sqlalchemy.ext.asyncio import AsyncSession

class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, payment_id: int | None, amount: float, commission: float, type: str, status: str):
        transaction = TransactionModel(
            user_id=user_id,
            payment_id=payment_id,
            amount=amount,
            commission=commission,
            type=TransactionType(type),
            status=TransactionStatus(status)
        )
        self.session.add(transaction)
        return transaction
