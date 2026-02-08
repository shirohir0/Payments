from application.dto.payment import DepositDTO
from core.settings import settings
from domain.entities.user import User
from domain.exceptions import UserNotFoundError
from infrastructure.db.models.payment import PaymentStatus
from infrastructure.db.models.transaction import TransactionStatus


class DepositBalanceUseCase:
    def __init__(self, user_repo, payment_repo, transaction_repo, session):
        self.user_repo = user_repo
        self.payment_repo = payment_repo
        self.transaction_repo = transaction_repo
        self.session = session

    async def execute(self, dto: DepositDTO) -> int:
        async with self.session.begin():
            user: User | None = await self.user_repo.get_by_id(dto.user_id)
            if not user:
                raise UserNotFoundError(f"User {dto.user_id} not found")

            dto.commission = round(dto.amount * settings.transaction_fee, 2)

            payment = await self.payment_repo.create(
                user_id=user.id,
                amount=dto.amount,
                commission=dto.commission,
                status=PaymentStatus.NEW,
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

        return payment.id
