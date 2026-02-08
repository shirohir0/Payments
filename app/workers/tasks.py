from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from app.core.settings import settings
from app.workers.celery_app import celery_app
from app.workers.payment_processor import PaymentProcessor

logger = logging.getLogger("payments_task")

_worker_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    global _worker_loop
    if _worker_loop is None:
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop.run_until_complete(coro)


@celery_app.task(bind=True, name="payments.process", max_retries=10)
def process_payment(self, payment_id: int) -> str:
    processor = PaymentProcessor()
    result = _run_async(processor.process(payment_id))

    if result == "retry":
        # exponential backoff based on celery retry count
        countdown = settings.gateway_backoff_base_seconds * (2 ** self.request.retries)
        countdown = min(countdown, settings.gateway_backoff_max_seconds)
        logger.warning("celery retry: payment_id=%s countdown=%s", payment_id, countdown)
        raise self.retry(countdown=countdown)

    return result
