from fastapi import APIRouter
from app.api.v1.gateway import router as gateway_router
from app.api.v1.health import router as health_router
from app.api.v1.payments import router as payments_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")

router.include_router(payments_router)
router.include_router(users_router)
router.include_router(health_router)
router.include_router(gateway_router)
