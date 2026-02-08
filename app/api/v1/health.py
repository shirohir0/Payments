from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.db.session import session_depends

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(session: session_depends):
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return {"status": status, "database": "ok" if db_ok else "unavailable"}
