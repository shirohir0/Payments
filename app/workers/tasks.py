from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from app.core.settings import settings
from app.workers.celery_app import celery_app
from app.workers.payment_processor import PaymentProcessor

logger = logging.getLogger("payments_task")


@celery_app.task(bind=True, name="payments.process", max_retries=10)
def process_payment(self, payment_id: int) -> str:
    processor = PaymentProcessor()
    result = asyncio.run(processor.process(payment_id))

    if result == "retry":
        # exponential backoff based on celery retry count
        countdown = settings.gateway_backoff_base_seconds * (2 ** self.request.retries)
        countdown = min(countdown, settings.gateway_backoff_max_seconds)
        logger.warning("celery retry: payment_id=%s countdown=%s", payment_id, countdown)
        raise self.retry(countdown=countdown)

    return result
