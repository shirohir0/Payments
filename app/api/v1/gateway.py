import asyncio
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/gateway", tags=["Gateway"])


class GatewayChargeRequest(BaseModel):
    payment_id: str
    user_id: str
    amount: str


@router.post("/charge")
async def charge(_: GatewayChargeRequest) -> dict:
    roll = random.random()
    if roll < 0.10:
        await asyncio.sleep(3)
        return {"status": "timeout"}
    if roll < 0.35:
        raise HTTPException(status_code=502, detail="Gateway error")
    return {"status": "approved"}
