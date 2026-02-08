import httpx

from core.settings import settings
from infrastructure.payment_gateway.base import PaymentGatewayClient


class HttpPaymentGatewayClient(PaymentGatewayClient):
    def __init__(self) -> None:
        timeout = httpx.Timeout(settings.payment_gateway_timeout_s)
        self._client = httpx.AsyncClient(timeout=timeout)

    async def charge(self, payment_id: int, user_id: int, amount: float) -> None:
        payload = {
            "payment_id": payment_id,
            "user_id": user_id,
            "amount": amount,
        }
        response = await self._client.post(settings.payment_gateway_url, json=payload)
        response.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
