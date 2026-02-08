import logging

from fastapi import APIRouter

from app.core.metrics import metrics
from app.api.v1.schemas.monitoring import MetricsResponse

router = APIRouter(prefix="/metrics", tags=["Metrics"])
logger = logging.getLogger("metrics_api")


@router.get("", summary="Метрики", response_model=MetricsResponse)
async def get_metrics():
    data = await metrics.snapshot()
    logger.info("metrics snapshot: keys=%s", len(data))
    return data
