from fastapi import APIRouter, Depends

from app.api.v1.dlq import router as dlq_router
from app.api.v1.health import router as health_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.payments import router as payments_router
from app.api.v1.users import router as users_router
from app.core.security import require_api_key

router = APIRouter(prefix="/api/v1")
router.include_router(health_router)
for protected_router in (payments_router, users_router, dlq_router, metrics_router):
    router.include_router(protected_router, dependencies=[Depends(require_api_key)])
