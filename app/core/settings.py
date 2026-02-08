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

    # ===============================
    # External services
    # ===============================
    payment_gateway_url: str

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
