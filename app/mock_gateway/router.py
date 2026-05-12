"""Deterministic local provider double with durable idempotency receipts."""

import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.outbox import GatewayReceipt
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/mock-gateway", tags=["MockGateway"])


class GatewayPaymentSchema(BaseModel):
    payment_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    commission: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    type: Literal["deposit", "withdraw"]


@router.post("/pay")
async def mock_pay(
    data: GatewayPaymentSchema,
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
):
    normalized = data.model_dump(mode="json")
    normalized["amount"] = format(data.amount, ".2f")
    normalized["commission"] = format(data.commission, ".2f")
    fingerprint = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
    async with session.begin():
        await session.execute(
            insert(GatewayReceipt)
            .values(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                payment_id=data.payment_id,
            )
            .on_conflict_do_nothing(index_elements=[GatewayReceipt.idempotency_key])
        )
        receipt = await session.scalar(
            select(GatewayReceipt).where(
                GatewayReceipt.idempotency_key == idempotency_key,
            )
        )
        if receipt is None:
            raise HTTPException(503, "Receipt unavailable")
        if receipt.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key payload conflict")
    return {
        "status": "success",
        "payment_id": data.payment_id,
        "reference": f"mock-{data.payment_id}",
    }
