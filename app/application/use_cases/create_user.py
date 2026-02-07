from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.user import User
from infrastructure.repositories.user import UserRepository


class CreateUserUseCase:
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
    ):
        self.session = session
        self.user_repo = user_repo

    async def execute(self, balance: float) -> User:
        # создаём доменную сущность
        user = User(id=None, balance=balance)

        # сохраняем через репозиторий
        user = await self.user_repo.add(user)

        # коммит транзакции
        await self.session.commit()

        return user
