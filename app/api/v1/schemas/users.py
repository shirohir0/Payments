from pydantic import BaseModel, Field


class CreateUserSchema(BaseModel):
    balance: float = Field(ge=0, description="Стартовый баланс")


class UserResponseSchema(BaseModel):
    id: int
    balance: float
