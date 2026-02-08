from app.application.dto.payment import DepositDTO
from app.core.settings import settings
from app.domain.entities.user import User
from app.domain.exceptions import UserNotFoundError
from app.infrastructure.db.models.payment import PaymentStatus
from app.infrastructure.db.models.transaction import TransactionStatus
from app.core.metrics import metrics
from app.workers.queue import enqueue_payment


class DepositBalanceUseCase:
    def __init__(self, user_repo, payment_repo, transaction_repo, session):
        self.user_repo = user_repo
        self.payment_repo = payment_repo
        self.transaction_repo = transaction_repo
        self.session = session

    async def execute(self, dto: DepositDTO) -> int:
        async with self.session.begin():
            logger = __import__("logging").getLogger("usecase.deposit")
            user: User | None = await self.user_repo.get_by_id(dto.user_id)
            if not user:
                raise UserNotFoundError(f"User {dto.user_id} not found")

            if dto.idempotency_key:
                existing = await self.payment_repo.get_by_idempotency_key(
                    user_id=user.id,
                    key=dto.idempotency_key,
                )
                if existing:
                    await metrics.inc("idempotency_hits_total")
                    logger.info("idempotency hit: user_id=%s payment_id=%s", user.id, existing.id)
                    return existing.id

            dto.commission = round(dto.amount * settings.transaction_fee, 2)

            payment = await self.payment_repo.create(
                user_id=user.id,
                amount=dto.amount,
                commission=dto.commission,
                status=PaymentStatus.NEW,
                idempotency_key=dto.idempotency_key,
            )

            await self.session.flush()

            await self.transaction_repo.create(
                user_id=user.id,
                payment_id=payment.id,
                amount=dto.amount,
                commission=dto.commission,
                type="deposit",
                status=TransactionStatus.PROCESSING.value,
            )

            enqueue_payment(payment.id)
            await metrics.inc("payments_task_enqueued_total")
            logger.info("payment created: type=deposit payment_id=%s user_id=%s amount=%s commission=%s",
                        payment.id, user.id, dto.amount, dto.commission)

        return payment.id
