from fastapi import APIRouter
from api.v1.payments import router as payments_router
from api.v1.users import router as users_router
from api.v1.mock_gateway import router as mock_gateway_router

router = APIRouter(prefix='/api/v1')

router.include_router(payments_router)
router.include_router(users_router)
router.include_router(mock_gateway_router)
