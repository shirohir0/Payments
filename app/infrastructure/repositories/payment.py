from infrastructure.db.models.payment import PaymentModel, PaymentStatus
from sqlalchemy.ext.asyncio import AsyncSession

class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, amount: float, commission: float):
        payment = PaymentModel(
            user_id=user_id,
            amount=amount,
            commission=commission,
            status=PaymentStatus.SUCCESS
        )
        self.session.add(payment)
        return payment
