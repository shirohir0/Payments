"""Exercise real schema changes only in an explicitly isolated migration database."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEAD = "0004_durable_delivery"
LEGACY = "0002_add_task_and_dlq"


def _checked_url(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername != "postgresql+asyncpg" or not (parsed.database or "").endswith("_test"):
        raise RuntimeError(
            "Migration tests require an isolated PostgreSQL database ending in _test"
        )
    other_url = os.environ.get("TEST_DATABASE_URL")
    if other_url:
        other = make_url(other_url)
        if (parsed.host, parsed.port, parsed.database) == (other.host, other.port, other.database):
            raise RuntimeError("Migration tests must not reset the normal integration database")
    return url


async def _sql(url: str, statements: list[str]) -> list[list[dict]]:
    engine = create_async_engine(_checked_url(url), poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            output = []
            for statement in statements:
                result = await connection.execute(text(statement))
                output.append(list(result.mappings()) if result.returns_rows else [])
            return output
    finally:
        await engine.dispose()


def _execute(url: str, *statements: str) -> list[list[dict]]:
    return asyncio.run(_sql(url, list(statements)))


@pytest.fixture
def migration_database_url():
    url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_MIGRATION_DATABASE_URL to a dedicated migration database ending in _test"
        )
    url = _checked_url(url)
    # This database is separate from application integration tests. Never infer
    # its URL from DATABASE_URL or a workstation's environment file.
    _execute(url, "DROP SCHEMA IF EXISTS public CASCADE", "CREATE SCHEMA public")
    try:
        yield url
    finally:
        _execute(url, "DROP SCHEMA IF EXISTS public CASCADE", "CREATE SCHEMA public")


def _alembic(url: str, *arguments: str, expected_success: bool = True):
    environment = os.environ.copy()
    environment.update(
        DATABASE_URL=_checked_url(url),
        APP_ENV="test",
        DEBUG="false",
        DB_ECHO="false",
        AUTO_CREATE_TABLES="false",
        PAYMENT_GATEWAY_URL="https://provider.invalid",
        API_KEY="migration-test-api-key-32-characters",
        GATEWAY_TIMEOUT_SECONDS="5",
        WORKER_PROCESSING_TIMEOUT_SECONDS="90",
        CELERY_TASK_TIME_LIMIT_SECONDS="60",
        CELERY_TASK_SOFT_TIME_LIMIT_SECONDS="45",
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(PROJECT_ROOT / "alembic.ini"), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    detail = result.stdout + result.stderr
    if expected_success:
        assert result.returncode == 0, detail
    else:
        assert result.returncode != 0, "Migration unexpectedly succeeded"
    return detail


def test_empty_database_upgrade_check_downgrade_and_upgrade(migration_database_url):
    url = migration_database_url
    _alembic(url, "upgrade", "head")
    _alembic(url, "check")
    assert _execute(url, "SELECT version_num FROM alembic_version")[0] == [{"version_num": HEAD}]
    _alembic(url, "downgrade", "base")
    assert (
        _execute(
            url,
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'",
        )[0]
        == []
    )
    _alembic(url, "upgrade", "head")
    _alembic(url, "check")


def test_legacy_task_survives_upgrade_and_pending_payment_is_quarantined(migration_database_url):
    url = migration_database_url
    _alembic(url, "upgrade", LEGACY)
    _execute(
        url,
        "INSERT INTO users (id, balance) VALUES (7, 102.00)",
        """INSERT INTO payments
            (id, user_id, amount, commission, status, attempts, last_error, locked_at, next_retry_at)
            VALUES (11, 7, 1.00, 0.02, 'processing', 2, 'legacy-provider-timeout',
                    now() - interval '2 minutes', now() - interval '1 minute')""",
        """INSERT INTO transactions (id, user_id, payment_id, amount, commission, type, status)
            VALUES (13, 7, 11, 1.00, 0.02, 'withdraw', 'processing')""",
        """INSERT INTO payment_tasks
            (id, payment_id, status, attempts, last_error, locked_at, next_retry_at)
            VALUES (17, 11, 'processing', 3, 'legacy-task-timeout',
                    now() - interval '2 minutes', now() - interval '1 minute')""",
    )
    old_task = _execute(url, "SELECT * FROM payment_tasks WHERE id = 17")[0][0]
    _alembic(url, "upgrade", "head")
    _alembic(url, "check")

    tables, archived, payment, wallet, event, ready, receipts = _execute(
        url,
        "SELECT to_regclass('payment_tasks') AS old_name, to_regclass('legacy_payment_tasks') AS archive",
        "SELECT * FROM legacy_payment_tasks WHERE id = 17",
        "SELECT operation, status, attempts, funds_reserved, last_error, locked_at, next_retry_at FROM payments WHERE id = 11",
        "SELECT balance, reserved_balance FROM users WHERE id = 7",
        "SELECT payment_id, completed_at, published_at, lease_until, last_error FROM payment_outbox",
        "SELECT count(*) AS count FROM payment_outbox WHERE completed_at IS NULL AND available_at <= now()",
        "SELECT count(*) AS count FROM mock_gateway_receipts",
    )
    assert tables == [{"old_name": None, "archive": "legacy_payment_tasks"}]
    assert archived == [old_task]
    assert payment[0]["operation"] == "withdraw"
    assert payment[0]["status"] == "processing"
    assert payment[0]["attempts"] == 2
    assert payment[0]["funds_reserved"] is False
    assert payment[0]["locked_at"] is payment[0]["next_retry_at"] is None
    assert payment[0]["last_error"].startswith("reconciliation_required:legacy_")
    assert str(wallet[0]["balance"]) == "102.00"
    assert str(wallet[0]["reserved_balance"]) == "0.00"
    assert event[0]["payment_id"] == 11
    assert event[0]["completed_at"] is not None
    assert event[0]["published_at"] is event[0]["lease_until"] is None
    assert event[0]["last_error"] == payment[0]["last_error"]
    assert ready == receipts == [{"count": 0}]

    failure = _alembic(url, "downgrade", "0003_payment_guarantees", expected_success=False)
    assert "Refusing downgrade" in failure
    version, preserved_task, preserved_event = _execute(
        url,
        "SELECT version_num FROM alembic_version",
        "SELECT * FROM legacy_payment_tasks WHERE id = 17",
        "SELECT payment_id, completed_at, published_at, lease_until, last_error FROM payment_outbox",
    )
    assert version == [{"version_num": HEAD}]
    assert preserved_task == archived
    assert preserved_event == event


@pytest.mark.parametrize("invalid_state", ["missing_transaction", "duplicate_transactions"])
def test_inconsistent_legacy_payments_fail_upgrade_without_changing_schema(
    migration_database_url, invalid_state
):
    url = migration_database_url
    _alembic(url, "upgrade", LEGACY)
    _execute(
        url,
        "INSERT INTO users (id, balance) VALUES (7, 102.00)",
        "INSERT INTO payments (id, user_id, amount, commission) VALUES (11, 7, 1.00, 0.02)",
    )
    if invalid_state == "duplicate_transactions":
        _execute(
            url,
            """INSERT INTO transactions (user_id, payment_id, amount, commission, type, status)
                VALUES (7, 11, 1.00, 0.02, 'withdraw', 'processing'),
                       (7, 11, 1.00, 0.02, 'withdraw', 'processing')""",
        )
    failure = _alembic(url, "upgrade", "head", expected_success=False)
    assert (
        "Reconcile payments without transactions" in failure
        or "Resolve duplicate payment transactions" in failure
    )
    version, columns, payment_count = _execute(
        url,
        "SELECT version_num FROM alembic_version",
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'reserved_balance'",
        "SELECT count(*) AS count FROM payments WHERE id = 11",
    )
    assert version == [{"version_num": LEGACY}]
    assert columns == []
    assert payment_count == [{"count": 1}]
