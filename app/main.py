from fastapi import FastAPI

from app.api.v1 import router
from app.core.dependencies import lifespan
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(lifespan=lifespan)

app.include_router(router)
