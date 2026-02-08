from api.v1 import router
from core.settings import settings
from fastapi import FastAPI
from api.middleware.db_errors import DBExceptionMiddleware

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app = FastAPI()

app.include_router(router)
app.add_middleware(DBExceptionMiddleware)

# from infrastructure.db.base import Base
# from infrastructure.db.session import engine

# @app.on_event("startup")
# async def startup():
#     async with engine.begin() as conn:
#         print("created tables")
#         await conn.run_sync(Base.metadata.create_all)




