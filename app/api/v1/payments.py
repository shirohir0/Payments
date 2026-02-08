from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.application.dto.payment import PaymentCreateRequest, PaymentResponse, PaymentStatusResponse
from app.core.dependencies import (
    get_create_payment_use_case,
    get_payment_status_use_case,
    get_queue_producer,
)
from app.domain.exceptions import NotFoundError

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", response_model=PaymentResponse)
async def create_payment(payload: PaymentCreateRequest) -> PaymentResponse:
    use_case = get_create_payment_use_case()
    queue = get_queue_producer()
    try:
        payment = await use_case.execute(payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await queue.enqueue(payment.id)
    return payment


@router.get("/{payment_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status(payment_id: UUID) -> PaymentStatusResponse:
    use_case = get_payment_status_use_case()
    try:
        return await use_case.execute(payment_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
