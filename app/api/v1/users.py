from fastapi import APIRouter

from app.api.v1.schemas.users import CreateUserSchema
from app.infrastructure.repositories.user import UserRepository
from app.application.use_cases.create_user import CreateUserUseCase
from app.infrastructure.db.session import session_depends

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/")
async def create_user(
    data: CreateUserSchema,
    session: session_depends,
):
    repo = UserRepository(session)
    use_case = CreateUserUseCase(session, repo)

    user = await use_case.execute(data.balance)

    return user
