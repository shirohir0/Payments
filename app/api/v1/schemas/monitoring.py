from typing import Optional

from pydantic import BaseModel, Field, RootModel


class HealthResponse(BaseModel):
    status: str = Field(..., description="ok | degraded")
    database: str = Field(..., description="ok | unavailable")


class DlqItemResponse(BaseModel):
    id: int
    payment_id: int
    user_id: int
    amount: float
    commission: float
    payment_type: str
    error: str
    attempts: int
    created_at: Optional[str] = None


class MetricsResponse(RootModel[dict[str, int]]):
    pass
