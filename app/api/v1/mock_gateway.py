import asyncio
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.settings import settings

router = APIRouter(prefix="/mock-gateway", tags=["MockGateway"])


class GatewayPaymentSchema(BaseModel):
    payment_id: int = Field(..., gt=0)
    user_id: int = Field(..., gt=0)
    amount: float
    commission: float
    type: str


@router.post("/pay")
async def mock_pay(data: GatewayPaymentSchema):
    roll = random.random()

    # 10% timeout
    if roll < 0.10:
        await asyncio.sleep(settings.gateway_timeout_seconds + 0.5)
        return {"status": "timeout"}

    # 25% error
    if roll < 0.35:
        raise HTTPException(status_code=502, detail="gateway_error")

    return {"status": "ok"}
