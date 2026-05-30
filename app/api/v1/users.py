from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.v1.schemas.users import CreateUserSchema, UserResponseSchema
from app.application.use_cases.create_user import CreateUserUseCase
from app.core.dependencies import get_create_user_use_case, get_user_repo
from app.infrastructure.repositories.user import UserRepository

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", summary="Создать пользователя", response_model=UserResponseSchema)
async def create_user(
    data: CreateUserSchema,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
):
    user = await use_case.execute(data.balance)
    return user


@router.get("/{user_id}", summary="Account balance and reservations")
async def get_user(
    user_id: Annotated[int, Path(gt=0, le=9223372036854775807)],
    repo: Annotated[UserRepository, Depends(get_user_repo)],
):
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "balance": format(user.balance, ".2f"),
        "reserved_balance": format(user.reserved_balance, ".2f"),
        "available_balance": format(user.balance - user.reserved_balance, ".2f"),
    }
