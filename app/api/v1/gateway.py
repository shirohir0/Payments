import asyncio
import random

from fastapi import APIRouter, HTTPException

from core.settings import settings


router = APIRouter(prefix="/gateway", tags=["Gateway"])


@router.post("/pay")
async def simulate_payment_gateway() -> dict:
    failure_roll = random.random()

    if failure_roll < settings.gateway_timeout_rate:
        await asyncio.sleep(settings.payment_gateway_timeout_s + 0.5)

    if failure_roll < settings.gateway_timeout_rate + settings.gateway_error_rate:
        raise HTTPException(status_code=502, detail="Gateway error")

    return {"status": "ok"}
