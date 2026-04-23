import httpx
import pytest

from app.infrastructure.payment_gateway.http import PaymentGatewayClient

PAYLOAD = {
    "payment_id": 123,
    "user_id": 7,
    "amount": "1.00",
    "commission": "0.02",
    "type": "withdraw",
}


@pytest.mark.asyncio
async def test_gateway_reuses_stable_key_and_exact_decimal_payload():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"status": "success", "payment_id": 123})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        gateway = PaymentGatewayClient("http://provider/payments/", client=http)
        assert (await gateway.charge(PAYLOAD)).success
        assert (await gateway.charge(PAYLOAD)).success
    assert requests[0].headers["Idempotency-Key"] == requests[1].headers["Idempotency-Key"]
    assert requests[0].content == requests[1].content
    assert b'"amount":"1.00"' in requests[0].content
    assert requests[0].url.path == "/payments/pay"


@pytest.mark.parametrize(
    "body",
    [None, {"status": "timeout"}, {"status": "ok"}, {"status": "success", "payment_id": 999}],
)
@pytest.mark.asyncio
async def test_http_success_without_confirmed_matching_payment_is_unknown(body):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=body),
        )
    ) as http:
        result = await PaymentGatewayClient("http://provider", client=http).charge(PAYLOAD)
    assert not result.success
    assert result.uncertain
    assert result.retryable


@pytest.mark.asyncio
async def test_non_json_success_is_unknown():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="temporarily unavailable"),
        )
    ) as http:
        result = await PaymentGatewayClient("http://provider", client=http).charge(PAYLOAD)
    assert result.uncertain
    assert not result.success


@pytest.mark.parametrize(
    "code,retryable,uncertain",
    [
        (400, False, False),
        (401, False, False),
        (422, False, False),
        (429, True, False),
        (503, True, True),
        (408, True, True),
        (409, False, True),
        (302, False, True),
    ],
)
@pytest.mark.asyncio
async def test_gateway_distinguishes_decline_retry_and_uncertain_outcome(
    code, retryable, uncertain
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(code),
        )
    ) as http:
        result = await PaymentGatewayClient("http://provider", client=http).charge(PAYLOAD)
    assert not result.success
    assert result.retryable is retryable
    assert result.uncertain is uncertain


@pytest.mark.parametrize(
    "exception_type,error",
    [(httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "transport_error")],
)
@pytest.mark.asyncio
async def test_transport_failure_never_means_payment_declined(exception_type, error):
    def handler(request):
        raise exception_type("sensitive details must not leak", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await PaymentGatewayClient("http://provider", client=http).charge(PAYLOAD)
    assert result.error == error
    assert result.uncertain and result.retryable
