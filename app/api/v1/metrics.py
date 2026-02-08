from fastapi import APIRouter

from app.core.metrics import metrics

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
async def get_metrics():
    return await metrics.snapshot()
