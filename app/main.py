from api.middleware.db_errors import DBExceptionMiddleware
from api.v1 import router
from core.settings import settings
from fastapi import FastAPI

from infrastructure.db.base import Base
from infrastructure.db.session import engine
from workers.payment_worker import PaymentWorker

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(router)
app.add_middleware(DBExceptionMiddleware)


@app.on_event("startup")
async def startup():
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    worker = PaymentWorker()
    app.state.payment_worker = worker
    await worker.start()


@app.on_event("shutdown")
async def shutdown():
    worker = getattr(app.state, "payment_worker", None)
    if worker:
        await worker.stop()




