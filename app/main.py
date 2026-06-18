import re
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request

from app.api.exception_handlers import register_exception_handlers
from app.api.v1 import router
from app.api.v1.health import readiness
from app.api.v1.metrics import prometheus_metrics
from app.core.logging import request_id_context, setup_logging
from app.core.metrics import metrics
from app.core.security import require_api_key
from app.core.settings import settings
from app.infrastructure.db.session import engine

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema changes are exclusively managed by Alembic.
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Internal payment processing API with durable dispatch and explicit reconciliation.",
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", incoming) else uuid4().hex
    token = request_id_context.set(request_id)
    started = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "__unmatched__")
        if route not in {"/metrics", "/health", "/ready", "/api/v1/health"}:
            method = (
                request.method
                if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER"
            )
            metrics.requests.labels(method, route, str(status)).observe(perf_counter() - started)
        request_id_context.reset(token)


@app.get("/health", tags=["Health"])
async def liveness():
    return {"status": "ok"}


app.add_api_route("/ready", readiness, methods=["GET"], tags=["Health"])
app.add_api_route(
    "/metrics",
    prometheus_metrics,
    methods=["GET"],
    dependencies=[Depends(require_api_key)],
    include_in_schema=False,
)
register_exception_handlers(app)
app.include_router(router)
