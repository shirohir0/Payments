from __future__ import annotations

from celery import Celery

from app.core.settings import settings

celery_app = Celery(
    "payments",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="payments",
    broker_connection_retry_on_startup=True,
    task_time_limit=settings.celery_task_time_limit_seconds,
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
)

# Ensure tasks are registered
import app.workers.tasks  # noqa: E402,F401
