from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.payment import PaymentModel, PaymentStatus


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        amount: Decimal,
        commission: Decimal,
        status: PaymentStatus = PaymentStatus.NEW,
        idempotency_key: str | None = None,
        *,
        operation: str,
        funds_reserved: bool = False,
    ) -> PaymentModel:
        payment = PaymentModel(
            user_id=user_id,
            amount=amount,
            commission=commission,
            status=status,
            idempotency_key=idempotency_key,
            operation=operation,
            funds_reserved=funds_reserved,
        )
        self.session.add(payment)
        return payment

    async def get_by_id(self, payment_id: int) -> PaymentModel | None:
        return await self.session.get(PaymentModel, payment_id)

    async def get_by_idempotency_key(self, user_id: int, key: str) -> PaymentModel | None:
        result = await self.session.execute(
            select(PaymentModel).where(
                PaymentModel.user_id == user_id,
                PaymentModel.idempotency_key == key,
            )
        )
        return result.scalar_one_or_none()
