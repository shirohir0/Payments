import asyncio
import logging
import os
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/mock-gateway", tags=["MockGateway"])
logger = logging.getLogger("mock_gateway")


class GatewayPaymentSchema(BaseModel):
    payment_id: int = Field(..., gt=0)
    user_id: int = Field(..., gt=0)
    amount: float
    commission: float
    type: str


def _gateway_timeout_seconds() -> float:
    value = os.getenv("GATEWAY_TIMEOUT_SECONDS", "1.0")
    try:
        return float(value)
    except ValueError:
        return 1.0


@router.post("/pay")
async def mock_pay(data: GatewayPaymentSchema):
    roll = random.random()

    # 10% timeout
    if roll < 0.10:
        logger.warning("mock timeout: payment_id=%s", data.payment_id)
        await asyncio.sleep(_gateway_timeout_seconds() + 0.5)
        return {"status": "timeout"}

    # 25% error
    if roll < 0.35:
        logger.warning("mock error: payment_id=%s", data.payment_id)
        raise HTTPException(status_code=502, detail="gateway_error")

    logger.info("mock success: payment_id=%s", data.payment_id)
    return {"status": "ok"}
