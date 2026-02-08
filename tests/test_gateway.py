import httpx
import pytest

from app.infrastructure.payment_gateway.http import PaymentGatewayClient


class DummyResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class DummyClient:
    def __init__(self, response: DummyResponse | Exception):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.mark.asyncio
async def test_gateway_success(monkeypatch):
    client = PaymentGatewayClient(base_url="http://example")
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=None: DummyClient(DummyResponse(200)))

    result = await client.charge({"x": 1})
    assert result.success is True


@pytest.mark.asyncio
async def test_gateway_retryable_error(monkeypatch):
    client = PaymentGatewayClient(base_url="http://example")
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=None: DummyClient(DummyResponse(503)))

    result = await client.charge({"x": 1})
    assert result.success is False
    assert result.retryable is True


@pytest.mark.asyncio
async def test_gateway_non_retryable_error(monkeypatch):
    client = PaymentGatewayClient(base_url="http://example")
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=None: DummyClient(DummyResponse(400)))

    result = await client.charge({"x": 1})
    assert result.success is False
    assert result.retryable is False


@pytest.mark.asyncio
async def test_gateway_timeout(monkeypatch):
    client = PaymentGatewayClient(base_url="http://example")
    monkeypatch.setattr("httpx.AsyncClient", lambda timeout=None: DummyClient(httpx.TimeoutException("timeout")))

    result = await client.charge({"x": 1})
    assert result.success is False
    assert result.error == "timeout"
