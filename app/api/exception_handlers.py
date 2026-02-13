import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.domain.exceptions import UserInsufficientFundsError, UserNotFoundError

logger = logging.getLogger("api_exceptions")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(_: Request, exc: UserNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UserInsufficientFundsError)
    async def insufficient_funds_handler(_: Request, exc: UserInsufficientFundsError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, __: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "Conflict"})

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(_: Request, __: SQLAlchemyError):
        logger.exception("database error")
        return JSONResponse(status_code=500, content={"detail": "Database temporarily unavailable"})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception):
        logger.exception("unhandled error")
        return JSONResponse(status_code=500, content={"detail": str(exc)})
