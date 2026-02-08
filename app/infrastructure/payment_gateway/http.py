import httpx
from decimal import Decimal
from uuid import UUID

from app.application.interfaces.gateway import PaymentGateway
from app.domain.exceptions import GatewayError


class HttpPaymentGateway(PaymentGateway):
    def __init__(self, base_url: str, timeout_s: float) -> None:
        self._base_url = base_url
        self._timeout = timeout_s

    async def charge(self, payment_id: UUID, user_id: UUID, amount: Decimal) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    self._base_url,
                    json={
                        "payment_id": str(payment_id),
                        "user_id": str(user_id),
                        "amount": str(amount),
                    },
                )
                response.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                raise GatewayError("Payment gateway request failed") from exc
