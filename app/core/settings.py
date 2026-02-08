from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from pathlib import Path

class Settings(BaseSettings):
    # ===============================
    # Application
    # ===============================
    app_name: str = Field(default="Payment Service")
    app_env: str = Field(default="local")
    debug: bool = Field(default=False)

    # ===============================
    # Database
    # ===============================
    database_url: str
    auto_create_tables: bool = Field(default=False)

    # ===============================
    # External services
    # ===============================
    payment_gateway_url: str

    # ===============================
    # Queue (RabbitMQ / Celery)
    # ===============================
    celery_broker_url: str = Field(default="amqp://guest:guest@localhost:5672//")
    celery_result_backend: str = Field(default="rpc://")
    celery_task_time_limit_seconds: int = Field(default=30)
    celery_task_soft_time_limit_seconds: int = Field(default=25)

    gateway_timeout_seconds: float = Field(default=1.0)
    gateway_max_attempts: int = Field(default=3)
    gateway_backoff_base_seconds: float = Field(default=1.0)
    gateway_backoff_max_seconds: float = Field(default=30.0)
    gateway_backoff_jitter_seconds: float = Field(default=0.5)

    # ===============================
    # Worker
    # ===============================
    worker_poll_interval_seconds: float = Field(default=0.5)
    worker_processing_timeout_seconds: float = Field(default=30.0)

    # ===============================
    # Logging
    # ===============================
    log_level: str = Field(default="INFO")

    transaction_fee: float = Field(default=2)

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / '.env',
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
settings.transaction_fee = settings.transaction_fee / 100
