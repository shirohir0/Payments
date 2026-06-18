import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from kombu import Connection
from sqlalchemy import text

from app.core.settings import settings
from app.infrastructure.db.session import AsyncSessionLocal

router = APIRouter(prefix="/health", tags=["Health"])


async def check_database() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))


def check_broker() -> None:
    with Connection(
        settings.celery_broker_url, connect_timeout=settings.readiness_timeout_seconds
    ) as connection:
        connection.ensure_connection(max_retries=0)


async def readiness() -> JSONResponse:
    async def check(operation):
        try:
            await asyncio.wait_for(operation, timeout=settings.readiness_timeout_seconds)
            return "ok"
        except Exception:
            return "unavailable"

    database, broker = await asyncio.gather(
        check(check_database()), check(asyncio.to_thread(check_broker))
    )
    ready = database == broker == "ok"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "degraded", "database": database, "broker": broker},
    )


@router.get("", summary="Readiness: PostgreSQL and message broker")
async def health_check():
    return await readiness()
