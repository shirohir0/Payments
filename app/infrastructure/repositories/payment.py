from infrastructure.db.models.payment import PaymentModel, PaymentStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, amount: float, commission: float):
        payment = PaymentModel(
            user_id=user_id,
            amount=amount,
            commission=commission,
            status=PaymentStatus.NEW
        )
        self.session.add(payment)
        return payment

    async def get_by_id(self, payment_id: int) -> PaymentModel | None:
        return await self.session.get(PaymentModel, payment_id)

    async def claim_pending(self, limit: int = 10) -> list[PaymentModel]:
        result = await self.session.execute(
            select(PaymentModel)
            .where(PaymentModel.status == PaymentStatus.NEW)
            .order_by(PaymentModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        payments = result.scalars().all()
        for payment in payments:
            payment.status = PaymentStatus.PROCESSING
        return payments

    async def set_status(self, payment: PaymentModel, status: PaymentStatus) -> None:
        payment.status = status
        self.session.add(payment)
