from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.schemas.users import CreateUserSchema, UserResponseSchema
from app.application.use_cases.create_user import CreateUserUseCase
from app.core.dependencies import get_create_user_use_case

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", summary="Создать пользователя", response_model=UserResponseSchema)
async def create_user(
    data: CreateUserSchema,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
):
    user = await use_case.execute(data.balance)
    return user
