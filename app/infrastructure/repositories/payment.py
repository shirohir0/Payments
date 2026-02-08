from infrastructure.db.models.payment import PaymentModel, PaymentStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, amount: float, commission: float, status: PaymentStatus = PaymentStatus.NEW):
        payment = PaymentModel(
            user_id=user_id,
            amount=amount,
            commission=commission,
            status=status
        )
        self.session.add(payment)
        return payment

    async def get_by_id(self, payment_id: int) -> PaymentModel | None:
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        return result.scalar_one_or_none()
