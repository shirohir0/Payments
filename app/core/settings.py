from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings; Compose-only variables may share the environment file."""

    app_name: str = "Payment Service"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_version: str = "2.0.0"
    debug: bool = False
    api_key: SecretStr | None = None
    database_url: str
    auto_create_tables: bool = False
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=5, gt=0)
    db_statement_timeout_ms: int = Field(default=30000, ge=100)
    db_echo: bool = False
    payment_gateway_url: str
    gateway_api_key: SecretStr | None = None
    gateway_idempotency_namespace: str = Field(default="payments", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    gateway_timeout_seconds: float = Field(default=5, gt=0, le=60)
    gateway_max_attempts: int = Field(default=5, ge=1, le=20)
    gateway_backoff_base_seconds: float = Field(default=1, gt=0)
    gateway_backoff_max_seconds: float = Field(default=60, gt=0)
    gateway_backoff_jitter_seconds: float = Field(default=0.5, ge=0)
    celery_broker_url: str = "amqp://payments:payments-local@localhost:15673//"
    celery_result_backend: str | None = None
    celery_task_time_limit_seconds: int = Field(default=60, ge=1)
    celery_task_soft_time_limit_seconds: int = Field(default=45, ge=1)
    worker_poll_interval_seconds: float = Field(default=1, ge=0.05)
    worker_processing_timeout_seconds: int = Field(default=90, ge=1)
    outbox_poll_interval_seconds: float = Field(default=1, ge=0.05)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_publish_timeout_seconds: float = Field(default=10, gt=0, le=60)
    readiness_timeout_seconds: float = Field(default=3, gt=0, le=10)
    log_level: str = "INFO"
    transaction_fee_percent: Decimal = Field(
        default=Decimal("2"), alias="transaction_fee", ge=0, lt=100
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8-sig",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @model_validator(mode="after")
    def validate_deployment(self):
        if self.worker_processing_timeout_seconds <= self.gateway_timeout_seconds:
            raise ValueError("Processing lease must exceed the gateway timeout")
        if self.worker_processing_timeout_seconds <= self.celery_task_time_limit_seconds:
            raise ValueError("Processing lease must exceed the hard task time limit")
        if self.celery_task_soft_time_limit_seconds >= self.celery_task_time_limit_seconds:
            raise ValueError("Soft task limit must be lower than the hard task limit")
        if self.app_env in {"staging", "production"}:
            if self.api_key is None or len(self.api_key.get_secret_value()) < 32:
                raise ValueError(
                    "Staging and production require an API_KEY of at least 32 characters"
                )
            if self.api_key.get_secret_value() in {
                "payments-local-development-key-only",
                "test-service-api-key-32-characters",
            }:
                raise ValueError("Replace the published example API_KEY before deployment")
            if self.gateway_idempotency_namespace in {"payments", "payments-local"}:
                raise ValueError("Configure a permanent unique gateway idempotency namespace")
            if self.debug or self.db_echo or self.auto_create_tables:
                raise ValueError("Debug, SQL echo and automatic schema creation must be disabled")
            if not self.payment_gateway_url.startswith("https://"):
                raise ValueError("Staging and production require an HTTPS payment gateway")
        return self

    @property
    def transaction_fee(self) -> Decimal:
        return self.transaction_fee_percent / Decimal("100")


settings = Settings()
