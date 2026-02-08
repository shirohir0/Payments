import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    payment_gateway_url: str = os.getenv(
        "PAYMENT_GATEWAY_URL", "http://localhost:8000/api/v1/gateway/charge"
    )
    payment_gateway_timeout_s: float = float(os.getenv("PAYMENT_GATEWAY_TIMEOUT_S", "2"))
    gateway_max_attempts: int = int(os.getenv("PAYMENT_GATEWAY_MAX_ATTEMPTS", "3"))
    gateway_backoff_base: float = float(os.getenv("PAYMENT_GATEWAY_BACKOFF_BASE", "0.5"))
    payment_queue_maxsize: int = int(os.getenv("PAYMENT_QUEUE_MAXSIZE", "0"))
    commission_rate: float = float(os.getenv("COMMISSION_RATE", "0.02"))


settings = Settings()
