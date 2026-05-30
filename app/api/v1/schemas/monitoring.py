from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, RootModel


class HealthResponse(BaseModel):
    status: str = Field(..., description="ok | degraded")
    database: str = Field(..., description="ok | unavailable")


class DlqItemResponse(BaseModel):
    id: int
    payment_id: int
    user_id: int
    amount: Decimal
    commission: Decimal
    payment_type: str
    error: str
    attempts: int
    created_at: datetime | None = None


class MetricsResponse(RootModel[dict[str, int]]):
    pass
