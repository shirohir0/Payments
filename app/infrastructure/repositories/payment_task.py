from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.payment_task import PaymentTaskModel, PaymentTaskStatus


class PaymentTaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, payment_id: int) -> PaymentTaskModel:
        task = PaymentTaskModel(payment_id=payment_id)
        self.session.add(task)
        return task

    async def get_by_payment_id(self, payment_id: int) -> PaymentTaskModel | None:
        result = await self.session.execute(
            select(PaymentTaskModel).where(PaymentTaskModel.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    async def reserve_next(self, now: datetime, stuck_before: datetime) -> PaymentTaskModel | None:
        stmt = (
            select(PaymentTaskModel)
            .where(
                or_(
                    PaymentTaskModel.status == PaymentTaskStatus.NEW,
                    and_(
                        PaymentTaskModel.status == PaymentTaskStatus.PROCESSING,
                        PaymentTaskModel.locked_at.is_not(None),
                        PaymentTaskModel.locked_at < stuck_before,
                    ),
                )
            )
            .where(
                or_(
                    PaymentTaskModel.next_retry_at.is_(None),
                    PaymentTaskModel.next_retry_at <= now,
                )
            )
            .order_by(PaymentTaskModel.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
