from application.dto.payment import WithdrawDTO
from domain.entities.user import User
from domain.exceptions import UserNotFoundError, UserInsufficientFundsError
from core.settings import settings

class WithdrawBalanceUseCase:
    def __init__(self, user_repo, payment_repo, transaction_repo, session):
        self.user_repo = user_repo
        self.payment_repo = payment_repo
        self.transaction_repo = transaction_repo
        self.session = session

    async def execute(self, dto: WithdrawDTO) -> int:
        async with self.session.begin():  # атомарная транзакция
            # 1️⃣ Получаем пользователя
            user: User | None = await self.user_repo.get_by_id(dto.user_id)
            if not user:
                raise UserNotFoundError(f"User {dto.user_id} not found")

            # 2️⃣ Рассчёт комиссии 2%
            dto.commission = round(dto.amount * settings.transaction_fee, 2)
            total_amount = dto.amount + dto.commission

            # 3️⃣ Проверяем, что баланс позволяет снять
            if user.balance < total_amount:
                raise UserInsufficientFundsError("Insufficient funds for this withdrawal")

            # 4️⃣ Создаём Payment
            payment = await self.payment_repo.create(
                user_id=user.id,
                amount=dto.amount,
                commission=dto.commission
            )
            await self.session.flush()  # чтобы payment.id был доступен

            # 5️⃣ Создаём Transaction
            await self.transaction_repo.create(
                user_id=user.id,
                payment_id=payment.id,
                amount=dto.amount,
                commission=dto.commission,
                type="withdraw",
                status="processing"
            )

        # 6️⃣ Возвращаем ID платежа
        return payment.id
