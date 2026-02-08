from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.dependencies import get_user_repo

router = APIRouter(prefix="/users", tags=["Users"])


class UserCreateRequest(BaseModel):
    balance: Decimal = Field(default=Decimal("0"))


class UserResponse(BaseModel):
    id: UUID
    balance: Decimal


@router.post("", response_model=UserResponse)
async def create_user(payload: UserCreateRequest) -> UserResponse:
    user_repo = get_user_repo()
    user_id = uuid4()
    user = await user_repo.seed(user_id, payload.balance)
    return UserResponse(id=user.id, balance=user.balance)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID) -> UserResponse:
    user_repo = get_user_repo()
    user = await user_repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user.id, balance=user.balance)
