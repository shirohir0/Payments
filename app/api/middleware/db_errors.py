from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import asyncpg


class DBExceptionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        try:
            await self.app(scope, receive, send)

        except (
            SQLAlchemyError,
            asyncpg.PostgresError,
            ConnectionResetError,
        ) as e:

            response = JSONResponse(
                status_code=500,
                content={"detail": "Database temporarily unavailable"},
            )

            await response(scope, receive, send)
