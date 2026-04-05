import os

# Explicit test settings take precedence over any workstation environment file.
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["DB_ECHO"] = "false"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["GATEWAY_TIMEOUT_SECONDS"] = "5"
os.environ["WORKER_PROCESSING_TIMEOUT_SECONDS"] = "90"
os.environ["CELERY_TASK_TIME_LIMIT_SECONDS"] = "60"
os.environ["CELERY_TASK_SOFT_TIME_LIMIT_SECONDS"] = "45"
os.environ["API_KEY"] = "test-service-api-key-32-characters"
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://payments:payments-local@127.0.0.1:15432/payments_test"
)
os.environ.setdefault("PAYMENT_GATEWAY_URL", "https://provider.invalid")
