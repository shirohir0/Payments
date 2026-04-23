from celery import Celery
from kombu import Queue

from app.core.settings import settings

celery_app = Celery("payments", broker=settings.celery_broker_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    # RabbitMQ 4.3+ rejects transient, non-exclusive queues. Control mailboxes
    # (including inspect/mingle reply queues) and event subscriptions are
    # connection-scoped, so declare them exclusive rather than enabling the
    # deprecated broker feature. The payments task queue stays durable.
    control_queue_exclusive=True,
    control_queue_durable=False,
    event_queue_exclusive=True,
    event_queue_durable=False,
    worker_prefetch_multiplier=1,
    task_default_queue="payments",
    task_queues=(Queue("payments", durable=True),),
    task_default_delivery_mode="persistent",
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=settings.outbox_publish_timeout_seconds,
    broker_transport_options={
        "confirm_publish": True,
        "connect_timeout": settings.outbox_publish_timeout_seconds,
        "read_timeout": settings.outbox_publish_timeout_seconds,
        "write_timeout": settings.outbox_publish_timeout_seconds,
    },
    task_time_limit=settings.celery_task_time_limit_seconds,
    task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
)

import app.workers.tasks  # noqa: E402,F401
