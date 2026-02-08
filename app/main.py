from app.api.middleware.db_errors import DBExceptionMiddleware
from app.api.v1 import router
from app.core.settings import settings
from app.core.logging import setup_logging
from fastapi import FastAPI

from app.workers.payment_worker import PaymentWorker

setup_logging()

openapi_tags = [
    {"name": "Payments", "description": "Операции пополнения/списания и статус платежей."},
    {"name": "Users", "description": "Создание пользователей и работа с балансом."},
    {"name": "MockGateway", "description": "Имитация внешнего платежного шлюза."},
    {"name": "Health", "description": "Проверка состояния сервиса и базы данных."},
    {"name": "DLQ", "description": "Очередь неуспешных задач (Dead Letter Queue)."},
    {"name": "Metrics", "description": "Внутренние метрики сервиса."},
]

app = FastAPI(
    title=settings.app_name,
    description=(
        "Сервис обработки платежей с комиссией 2%, асинхронной фоновой обработкой, "
        "ретраями и интеграцией с платёжным шлюзом."
    ),
    version="1.0.0",
    debug=settings.debug,
    openapi_tags=openapi_tags,
)

app.include_router(router)
app.add_middleware(DBExceptionMiddleware)


@app.on_event("startup")
async def startup():
    worker = PaymentWorker()
    app.state.payment_worker = worker
    await worker.start()


@app.on_event("shutdown")
async def shutdown():
    worker = getattr(app.state, "payment_worker", None)
    if worker:
        await worker.stop()
