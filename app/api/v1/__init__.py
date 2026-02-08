from fastapi import APIRouter
from app.api.v1.payments import router as payments_router
from app.api.v1.users import router as users_router
from app.api.v1.health import router as health_router
from app.mock_gateway.router import router as mock_gateway_router
from app.api.v1.dlq import router as dlq_router

router = APIRouter(prefix='/api/v1')

router.include_router(payments_router)
router.include_router(users_router)
router.include_router(mock_gateway_router)
router.include_router(health_router)
router.include_router(dlq_router)
