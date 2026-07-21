import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def sessions():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_DATABASE_URL to an isolated migrated PostgreSQL database ending in _test"
        )
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("Integration tests require a dedicated database name ending in _test")
    engine = create_async_engine(url, pool_size=10, max_overflow=10)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, payments, transactions, payment_outbox, payment_dlq, payment_resolutions, mock_gateway_receipts RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
