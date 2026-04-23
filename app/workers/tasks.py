import asyncio
import logging
import os

import httpx
from celery.signals import worker_process_init, worker_process_shutdown

from app.infrastructure.db.session import engine
from app.infrastructure.payment_gateway.http import PaymentGatewayClient
from app.workers.celery_app import celery_app
from app.workers.payment_processor import PaymentProcessor

_worker_loop: asyncio.AbstractEventLoop | None = None
_http_client: httpx.AsyncClient | None = None
_owner_pid: int | None = None
logger = logging.getLogger("payments_tasks")


@worker_process_init.connect
def reset_after_fork(**_kwargs) -> None:
    global _worker_loop, _http_client, _owner_pid
    # Do not close the parent's live connections in a forked child.
    engine.sync_engine.dispose(close=False)
    _worker_loop = None
    _http_client = None
    _owner_pid = os.getpid()


@worker_process_shutdown.connect
def close_resources(**_kwargs) -> None:
    global _worker_loop, _http_client
    loop = _worker_loop
    try:
        if loop is not None and not loop.is_closed() and not loop.is_running():
            if _http_client is not None:
                loop.run_until_complete(_http_client.aclose())
            loop.run_until_complete(engine.dispose())
            loop.close()
        # A cold termination can interrupt a running loop. Never recursively
        # run it during shutdown; process exit closes descriptors and the
        # durable lease recovers any in-flight work in another process.
    except Exception as exc:
        logger.warning("worker cleanup interrupted error_type=%s", type(exc).__name__)
    finally:
        _worker_loop = None
        _http_client = None


@celery_app.task(name="payments.process", ignore_result=True)
def process_payment(payment_id: int) -> str:
    global _worker_loop, _http_client, _owner_pid
    if _owner_pid != os.getpid():
        reset_after_fork()
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    if _http_client is None:
        _http_client = httpx.AsyncClient(follow_redirects=False)
    processor = PaymentProcessor(gateway=PaymentGatewayClient(client=_http_client))
    # Retries and abandoned leases are scheduled durably in PostgreSQL, not
    # only in Celery messages which could be lost after a worker crash.
    return _worker_loop.run_until_complete(processor.process(payment_id))
