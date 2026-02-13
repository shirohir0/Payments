from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.v1 import router
from app.core.logging import setup_logging
from app.core.settings import settings
from app.infrastructure.db import models as _models  # noqa: F401
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import engine

setup_logging()

openapi_tags = [
    {"name": "Payments", "description": "Операции пополнения/списания и статус платежей."},
    {"name": "Users", "description": "Создание пользователей и работа с балансом."},
    {"name": "MockGateway", "description": "Имитация внешнего платёжного шлюза."},
    {"name": "Health", "description": "Проверка состояния сервиса и базы данных."},
    {"name": "DLQ", "description": "Очередь неуспешных задач (Dead Letter Queue)."},
    {"name": "Metrics", "description": "Внутренние метрики сервиса."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Сервис обработки платежей с комиссией 2%, асинхронной фоновой обработкой, "
        "ретраями и интеграцией с платёжным шлюзом."
    ),
    version=settings.app_version,
    debug=settings.debug,
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(router)
