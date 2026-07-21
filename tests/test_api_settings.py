from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.settings import Settings, settings
from app.main import app


def test_production_settings_require_strong_key_and_https():
    base = {
        "_env_file": None,
        "app_env": "production",
        "database_url": "postgresql+asyncpg://db/payments",
        "payment_gateway_url": "https://provider.example",
        "gateway_idempotency_namespace": "production-test-unique",
    }
    with pytest.raises(ValidationError, match="API_KEY"):
        Settings(**base, api_key="short")
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(**{**base, "payment_gateway_url": "http://provider.example"}, api_key="x" * 32)
    with pytest.raises(ValidationError, match="Debug"):
        Settings(**base, api_key="x" * 32, debug=True)
    value = Settings(**base, api_key="x" * 32, POSTGRES_DB="compose-only")
    assert value.transaction_fee.as_tuple().exponent < 0


def test_task_lease_must_exceed_http_timeout():
    with pytest.raises(ValidationError, match="lease"):
        Settings(_env_file=None, worker_processing_timeout_seconds=5, gateway_timeout_seconds=5)


def test_invalid_configuration_does_not_print_secrets(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PAYMENT_GATEWAY_URL", raising=False)
    secret = "SYNTHETIC-SECRET-THAT-MUST-NOT-APPEAR"
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, api_key=secret)
    assert secret not in str(error.value)


def test_business_routes_require_api_key(monkeypatch):
    monkeypatch.setattr(settings, "api_key", SecretStr("expected-key"))
    with TestClient(app) as client:
        assert client.get("/api/v1/payments/1").status_code == 401
        assert client.get("/api/v1/dlq", headers={"X-API-Key": "wrong"}).status_code == 401
        assert client.get("/api/v1/mock-gateway/pay").status_code == 404
        response = client.get("/health", headers={"X-Request-ID": "probe-123"})
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "probe-123"


@pytest.mark.parametrize("amount", ["0", "-1", "0.001", "NaN", "Infinity", "10000000000"])
def test_api_rejects_invalid_amount_without_database(amount):
    headers = {"X-API-Key": settings.api_key.get_secret_value(), "Idempotency-Key": "valid"}
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/payments/deposit", json={"user_id": 1, "deposit": amount}, headers=headers
        )
    assert response.status_code == 422


def test_missing_idempotency_key_is_invalid():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/payments/deposit",
            json={"user_id": 1, "deposit": "1.00"},
            headers={"X-API-Key": settings.api_key.get_secret_value()},
        )
    assert response.status_code == 422


def test_readiness_reports_database_failure(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.health.check_database", AsyncMock(side_effect=ConnectionError())
    )
    monkeypatch.setattr("app.api.v1.health.check_broker", lambda: None)
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert response.json()["broker"] == "ok"


def test_readiness_reports_broker_failure(monkeypatch):
    monkeypatch.setattr("app.api.v1.health.check_database", AsyncMock())

    def unavailable():
        raise ConnectionError()

    monkeypatch.setattr("app.api.v1.health.check_broker", unavailable)
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["broker"] == "unavailable"


def test_metrics_are_protected_and_include_persisted_worker_state(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.metrics.database_metrics",
        AsyncMock(return_value=b'payments_state{state="success"} 7\n'),
    )
    with TestClient(app) as client:
        assert client.get("/metrics").status_code == 401
        response = client.get(
            "/metrics", headers={"X-API-Key": settings.api_key.get_secret_value()}
        )
    assert response.status_code == 200
    assert "payments_state" in response.text


def test_internal_exceptions_do_not_leak_details():
    from app.core.dependencies import get_create_user_use_case

    class Broken:
        async def execute(self, _):
            raise RuntimeError("PRIVATE PROVIDER CREDENTIALS")

    app.dependency_overrides[get_create_user_use_case] = lambda: Broken()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/users/",
                json={"balance": "0.00"},
                headers={"X-API-Key": settings.api_key.get_secret_value()},
            )
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert "PRIVATE" not in response.text
    finally:
        app.dependency_overrides.clear()
