from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.payment_dlq import PaymentDLQModel


class PaymentDLQRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_payment_id(self, payment_id: int) -> PaymentDLQModel | None:
        result = await self.session.execute(
            select(PaymentDLQModel).where(PaymentDLQModel.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        payment_id: int,
        user_id: int,
        amount: float,
        commission: float,
        payment_type: str,
        error: str,
        attempts: int,
    ) -> PaymentDLQModel:
        record = PaymentDLQModel(
            payment_id=payment_id,
            user_id=user_id,
            amount=amount,
            commission=commission,
            payment_type=payment_type,
            error=error,
            attempts=attempts,
        )
        self.session.add(record)
        return record

    async def list_latest(self, limit: int = 50, offset: int = 0) -> list[PaymentDLQModel]:
        result = await self.session.execute(
            select(PaymentDLQModel)
            .order_by(PaymentDLQModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
