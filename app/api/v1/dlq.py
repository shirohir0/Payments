from fastapi import APIRouter, Query

from app.infrastructure.db.session import session_depends
from app.infrastructure.repositories.payment_dlq import PaymentDLQRepository

router = APIRouter(prefix="/dlq", tags=["DLQ"])


@router.get("")
async def list_dlq(
    session: session_depends,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    repo = PaymentDLQRepository(session)
    items = await repo.list_latest(limit=limit, offset=offset)
    return [
        {
            "id": item.id,
            "payment_id": item.payment_id,
            "user_id": item.user_id,
            "amount": float(item.amount),
            "commission": float(item.commission),
            "payment_type": item.payment_type,
            "error": item.error,
            "attempts": item.attempts,
            "created_at": item.created_at,
        }
        for item in items
    ]
