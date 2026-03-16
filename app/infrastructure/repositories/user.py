from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.infrastructure.db.models.user import UserModel


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, user: User) -> User:
        db_user = UserModel(balance=user.balance, reserved_balance=user.reserved_balance)
        self.session.add(db_user)
        await self.session.flush()
        return User(
            id=db_user.id, balance=db_user.balance, reserved_balance=db_user.reserved_balance
        )

    async def get_by_id(self, user_id: int) -> User | None:
        db_user = await self.session.get(UserModel, user_id)
        if db_user is None:
            return None
        return User(
            id=db_user.id, balance=db_user.balance, reserved_balance=db_user.reserved_balance
        )

    async def get_for_update(self, user_id: int) -> UserModel | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def save(self, user: User) -> None:
        db_user = await self.session.get(UserModel, user.id)
        if db_user is None:
            raise ValueError(f"User {user.id} not found in DB")
        db_user.balance = user.balance
        db_user.reserved_balance = user.reserved_balance
