from pydantic import BaseModel, Field


class CreateUserSchema(BaseModel):
    balance: float = Field(ge=0)
