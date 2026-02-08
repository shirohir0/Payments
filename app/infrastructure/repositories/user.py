from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.infrastructure.db.models.user import UserModel
from app.domain.entities.user import User

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------ Добавление нового пользователя ------------------
    async def add(self, user: User) -> User:
        db_user = UserModel(balance=user.balance)
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return User(id=db_user.id, balance=db_user.balance)

    # ------------------ Получение пользователя по ID ------------------
    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            return None
        return User(id=db_user.id, balance=db_user.balance)

    # ------------------ Сохранение изменений пользователя ------------------
    async def save(self, user: User) -> None:
        db_user = await self.session.get(UserModel, user.id)
        if not db_user:
            raise ValueError(f"User {user.id} not found in DB")
        db_user.balance = user.balance
        self.session.add(db_user)
