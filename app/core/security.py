import secrets
from typing import Annotated

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.settings import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(supplied: Annotated[str | None, Security(api_key_header)]) -> None:
    """Authenticate the trusted backend calling this internal payment service."""
    expected = settings.api_key
    if expected is None:
        return
    if supplied is None or not secrets.compare_digest(
        supplied.encode("utf-8"), expected.get_secret_value().encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
