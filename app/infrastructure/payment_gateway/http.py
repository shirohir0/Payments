from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from core.settings import settings


@dataclass
class GatewayResponse:
    success: bool
    error: str | None = None
    raw_status: int | None = None
    retryable: bool = True


class PaymentGatewayClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float | None = None):
        self.base_url = base_url or settings.payment_gateway_url.rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.gateway_timeout_seconds

    async def charge(self, payload: dict[str, Any]) -> GatewayResponse:
        url = f"{self.base_url}/pay"
        timeout = httpx.Timeout(self.timeout_seconds)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.TimeoutException:
            return GatewayResponse(success=False, error="timeout")
        except httpx.HTTPError as exc:
            return GatewayResponse(success=False, error=str(exc))

        if response.status_code >= 200 and response.status_code < 300:
            return GatewayResponse(success=True, raw_status=response.status_code)

        retryable = response.status_code >= 500 or response.status_code == 429
        return GatewayResponse(
            success=False,
            error=f"gateway_error_{response.status_code}",
            raw_status=response.status_code,
            retryable=retryable,
        )
