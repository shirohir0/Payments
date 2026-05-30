import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.domain.exceptions import (
    IdempotencyConflictError,
    InvalidIdempotencyKeyError,
    InvalidMoneyError,
    UserInsufficientFundsError,
    UserNotFoundError,
)

logger = logging.getLogger("api_exceptions")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(_: Request, exc: UserNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UserInsufficientFundsError)
    async def insufficient_funds_handler(_: Request, exc: UserInsufficientFundsError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(_: Request, exc: IdempotencyConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidMoneyError)
    @app.exception_handler(InvalidIdempotencyKeyError)
    async def invalid_command_handler(_: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, __: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": "Conflicting operation"})

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(_: Request, __: SQLAlchemyError):
        logger.exception("database operation failed")
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, __: Exception):
        logger.exception("unhandled application error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
