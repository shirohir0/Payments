from fastapi import FastAPI
from api.v1 import router
from core.settings import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(router)

# from infrastructure.db.base import Base
# from infrastructure.db.session import engine

# @app.on_event("startup")
# async def startup():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)
