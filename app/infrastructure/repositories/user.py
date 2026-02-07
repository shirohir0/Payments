from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.db.models.user import UserModel
from domain.entities.user import User

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, user: User) -> User:
        db_user = UserModel(balance=user.balance)
        self.session.add(db_user)
        await self.session.commit()
        await self.session.refresh(db_user)
        return User(id=db_user.id, balance=db_user.balance)
