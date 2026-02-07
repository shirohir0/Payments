from fastapi import APIRouter
from api.v1.payments import router as payments_router
from api.v1.users import router as users_router

router = APIRouter(prefix='/api/v1')

router.include_router(payments_router)
router.include_router(users_router)
