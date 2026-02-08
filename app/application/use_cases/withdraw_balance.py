from app.application.dto.payment import WithdrawDTO
from app.core.settings import settings
from app.domain.entities.user import User
from app.domain.exceptions import UserInsufficientFundsError, UserNotFoundError
from app.infrastructure.db.models.payment import PaymentStatus
from app.infrastructure.db.models.transaction import TransactionStatus


class WithdrawBalanceUseCase:
    def __init__(self, user_repo, payment_repo, transaction_repo, session):
        self.user_repo = user_repo
        self.payment_repo = payment_repo
        self.transaction_repo = transaction_repo
        self.session = session

    async def execute(self, dto: WithdrawDTO) -> int:
        insufficient_funds = False
        failed_payment_id: int | None = None

        async with self.session.begin():
            user: User | None = await self.user_repo.get_by_id(dto.user_id)
            if not user:
                raise UserNotFoundError(f"User {dto.user_id} not found")

            if dto.idempotency_key:
                existing = await self.payment_repo.get_by_idempotency_key(
                    user_id=user.id,
                    key=dto.idempotency_key,
                )
                if existing:
                    return existing.id

            dto.commission = round(dto.amount * settings.transaction_fee, 2)
            total_amount = round(dto.amount + dto.commission, 2)

            if user.balance < total_amount:
                payment = await self.payment_repo.create(
                    user_id=user.id,
                    amount=dto.amount,
                    commission=dto.commission,
                    status=PaymentStatus.FAILED,
                    idempotency_key=dto.idempotency_key,
                )
                payment.last_error = "insufficient_funds"
                await self.session.flush()

                await self.transaction_repo.create(
                    user_id=user.id,
                    payment_id=payment.id,
                    amount=dto.amount,
                    commission=dto.commission,
                    type="withdraw",
                    status=TransactionStatus.FAILED.value,
                )

                insufficient_funds = True
                failed_payment_id = payment.id
            else:
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
                    type="withdraw",
                    status=TransactionStatus.PROCESSING.value,
                )

        if insufficient_funds:
            raise UserInsufficientFundsError(
                f"Insufficient funds for this withdrawal. payment_id={failed_payment_id}"
            )

        return payment.id
