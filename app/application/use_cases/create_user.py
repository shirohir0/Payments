from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.infrastructure.repositories.user import UserRepository


class CreateUserUseCase:
    def __init__(self, session: AsyncSession, user_repo: UserRepository):
        self.session = session
        self.user_repo = user_repo

    async def execute(self, balance: Decimal) -> User:
        user = User(id=None, balance=balance)
        async with self.session.begin():
            return await self.user_repo.add(user)
