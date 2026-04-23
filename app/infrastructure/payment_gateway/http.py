"""Adapter for an idempotent provider; timeout never implies a decline."""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.settings import settings


@dataclass(frozen=True)
class GatewayResponse:
    success: bool
    error: str | None = None
    raw_status: int | None = None
    retryable: bool = False
    uncertain: bool = False


class PaymentGatewayClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or settings.payment_gateway_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.gateway_timeout_seconds
        self.client = client

    async def charge(self, payload: dict[str, Any]) -> GatewayResponse:
        payment_id = payload["payment_id"]
        headers = {"Idempotency-Key": f"{settings.gateway_idempotency_namespace}:{payment_id}"}
        if settings.gateway_api_key:
            headers["Authorization"] = f"Bearer {settings.gateway_api_key.get_secret_value()}"
        try:
            if self.client is not None:
                response = await self.client.post(
                    f"{self.base_url}/pay",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(
                    timeout=self.timeout_seconds, follow_redirects=False
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/pay", json=payload, headers=headers
                    )
        except httpx.TimeoutException:
            return GatewayResponse(False, "timeout", retryable=True, uncertain=True)
        except httpx.HTTPError:
            return GatewayResponse(False, "transport_error", retryable=True, uncertain=True)
        status = response.status_code
        if 200 <= status < 300:
            try:
                body = response.json()
            except ValueError:
                body = None
            if (
                isinstance(body, dict)
                and body.get("status") == "success"
                and type(body.get("payment_id")) is int
                and body.get("payment_id") == payment_id
            ):
                return GatewayResponse(True, raw_status=status)
            return GatewayResponse(
                False, "invalid_gateway_response", status, retryable=True, uncertain=True
            )
        if status == 429:
            return GatewayResponse(False, "gateway_rate_limited", status, retryable=True)
        if status >= 500 or status == 408:
            return GatewayResponse(
                False, f"gateway_error_{status}", status, retryable=True, uncertain=True
            )
        if status == 409 or not 400 <= status < 500:
            return GatewayResponse(False, f"gateway_error_{status}", status, uncertain=True)
        # Provider contract: other 4xx responses definitively reject this key.
        return GatewayResponse(False, f"gateway_error_{status}", status)
