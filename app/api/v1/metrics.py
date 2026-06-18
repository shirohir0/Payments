import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest
from sqlalchemy import func, select

from app.api.v1.schemas.monitoring import MetricsResponse
from app.core.metrics import metrics
from app.core.settings import settings
from app.infrastructure.db.models.outbox import OutboxEvent
from app.infrastructure.db.models.payment import PaymentModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.db.session import AsyncSessionLocal

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("", response_model=MetricsResponse, summary="Local process event counters")
async def get_metrics():
    return await metrics.snapshot()


async def database_metrics() -> bytes:
    """Read durable state, including outcomes produced by independent Celery workers."""
    registry = CollectorRegistry()
    states = Gauge(
        "payments_state", "Persisted payment count by state", ["state"], registry=registry
    )
    attempts = Gauge(
        "payments_processing_attempts", "Persisted processing attempts", registry=registry
    )
    pending = Gauge(
        "payments_outbox_pending", "Unfinished durable dispatch rows", registry=registry
    )
    review = Gauge(
        "payments_reconciliation_required",
        "Payments requiring operator verification",
        registry=registry,
    )
    holds = Gauge(
        "payments_accounts_with_reservations", "Accounts holding reserved funds", registry=registry
    )
    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(PaymentModel.status, func.count()).group_by(PaymentModel.status)
        )
        for state, count in rows:
            states.labels(state.value).set(count)
        attempts.set(
            await session.scalar(select(func.coalesce(func.sum(PaymentModel.attempts), 0)))
        )
        pending.set(
            await session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.completed_at.is_(None))
            )
        )
        review.set(
            await session.scalar(
                select(func.count())
                .select_from(OutboxEvent)
                .where(OutboxEvent.last_error.like("reconciliation_required:%"))
            )
        )
        holds.set(
            await session.scalar(
                select(func.count()).select_from(UserModel).where(UserModel.reserved_balance > 0)
            )
        )
    return generate_latest(registry)


async def prometheus_metrics():
    try:
        persisted = await asyncio.wait_for(
            database_metrics(), timeout=settings.readiness_timeout_seconds
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Metrics database unavailable") from None
    return Response(content=metrics.render() + persisted, media_type=CONTENT_TYPE_LATEST)
