"""Persistent relay: python -m app.workers.outbox.

Publishing and DB commit cannot be atomic. Confirmation loss may duplicate a
message, so the processor must fence concurrent work and the provider must
honour its stable idempotency key.
"""

import asyncio
import logging
import signal
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import or_, select

from app.core.settings import settings
from app.infrastructure.db.models.outbox import OutboxEvent
from app.infrastructure.db.session import AsyncSessionLocal, engine
from app.workers.payment_processor import utcnow

logger = logging.getLogger("payment_outbox")


def publish_payment(payment_id: int) -> None:
    from app.workers.celery_app import celery_app

    celery_app.send_task(
        "payments.process",
        args=[payment_id],
        delivery_mode=2,
        retry=False,
        ignore_result=True,
        timeout=settings.outbox_publish_timeout_seconds,
        confirm_timeout=settings.outbox_publish_timeout_seconds,
    )


async def publish_batch(*, session_factory=None, publish=None) -> int:
    sessions = session_factory or AsyncSessionLocal
    publish = publish or publish_payment
    now = utcnow()
    claims: list[tuple[int, int, str]] = []
    async with sessions() as session, session.begin():
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.completed_at.is_(None),
                        OutboxEvent.available_at <= now,
                        or_(
                            OutboxEvent.relay_lease_until.is_(None),
                            OutboxEvent.relay_lease_until <= now,
                        ),
                        or_(OutboxEvent.lease_until.is_(None), OutboxEvent.lease_until <= now),
                    )
                    .order_by(OutboxEvent.available_at, OutboxEvent.id)
                    .limit(settings.outbox_batch_size)
                    .with_for_update(skip_locked=True),
                )
            ).all()
        )
        for event in events:
            token = str(uuid4())
            event.relay_token = token
            event.relay_lease_until = now + timedelta(
                seconds=settings.outbox_publish_timeout_seconds
            )
            event.attempts += 1
            claims.append((event.id, event.payment_id, token))
    published = 0
    for event_id, payment_id, token in claims:
        error = None
        try:
            # The broker publisher uses blocking Kombu I/O. Its transport
            # timeouts bound this thread; cancellation never marks a publish
            # complete and the relay lease safely expires for another relay.
            result = await asyncio.to_thread(publish, payment_id)
            if hasattr(result, "__await__"):
                await result
        except Exception as exc:
            logger.error(
                "outbox publish failed payment_id=%s error_type=%s", payment_id, type(exc).__name__
            )
            error = "broker_publish_failed"
        if error is None:
            published += 1
        async with sessions() as session, session.begin():
            event = await session.get(OutboxEvent, event_id, with_for_update=True)
            if event is None or event.relay_token != token or event.completed_at is not None:
                # A fast processor already took ownership; never overwrite its
                # retry schedule or completion with stale publisher state.
                continue
            finished = utcnow()
            event.relay_token = None
            event.relay_lease_until = None
            event.last_error = error
            if error is None:
                event.published_at = finished
                event.available_at = finished + timedelta(
                    seconds=settings.worker_processing_timeout_seconds
                )
            else:
                event.available_at = finished + timedelta(
                    seconds=min(2 ** min(event.attempts, 6), 60)
                )
    return published


async def run() -> None:
    from app.core.logging import setup_logging

    setup_logging()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:
            pass  # Windows development; production runs in Linux containers.
    try:
        while not stop.is_set():
            try:
                await publish_batch()
            except Exception:
                logger.exception("outbox polling failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.outbox_poll_interval_seconds)
            except TimeoutError:
                pass
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
