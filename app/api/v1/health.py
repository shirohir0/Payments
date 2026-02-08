import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.db.session import session_depends
from app.api.v1.schemas.monitoring import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])
logger = logging.getLogger("health_api")


@router.get("", summary="Health-check", response_model=HealthResponse)
async def health_check(session: session_depends):
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    logger.info("health_check status=%s db_ok=%s", status, db_ok)
    return {"status": status, "database": "ok" if db_ok else "unavailable"}
