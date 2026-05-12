from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.settings import settings
from app.infrastructure.db.session import AsyncSessionLocal, engine
from app.mock_gateway.router import router


@asynccontextmanager
async def lifespan(_app):
    if settings.app_env == "production":
        raise RuntimeError("The mock gateway must not run in production")
    yield
    await engine.dispose()


app = FastAPI(title="Local Payment Gateway", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}
