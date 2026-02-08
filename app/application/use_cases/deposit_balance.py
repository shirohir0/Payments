from application.dto.payment import DepositDTO
from domain.entities.user import User
from domain.exceptions import UserNotFoundError
from core.settings import settings

class DepositBalanceUseCase:
    def __init__(self, user_repo, payment_repo, transaction_repo, session):
        self.user_repo = user_repo
        self.payment_repo = payment_repo
        self.transaction_repo = transaction_repo
        self.session = session  # используем одну сессию для атомарной транзакции

    async def execute(self, dto: DepositDTO) -> int:
        async with self.session.begin():  # <-- атомарная транзакция
            # 1️⃣ Получаем пользователя
            user: User | None = await self.user_repo.get_by_id(dto.user_id)
            if not user:
                raise UserNotFoundError(f"User {dto.user_id} not found")

            # 2️⃣ Рассчёт комиссии 2%
            dto.commission = round(dto.amount * settings.transaction_fee, 2)

            # 3️⃣ Создаём Payment
            payment = await self.payment_repo.create(
                user_id=user.id,
                amount=dto.amount,
                commission=dto.commission
            )

            # 4️⃣ flush чтобы payment.id был доступен
            await self.session.flush()

            # 5️⃣ Создаём Transaction
            await self.transaction_repo.create(
                user_id=user.id,
                payment_id=payment.id,
                amount=dto.amount,
                commission=dto.commission,
                type="deposit",
                status="processing"
            )

        # 6️⃣ Возвращаем ID платежа
        return payment.id
