from decimal import Decimal
from functools import lru_cache
from typing import AsyncIterator

from app.application.use_cases.create_payment import CreatePaymentUseCase
from app.application.use_cases.get_payment_status import GetPaymentStatusUseCase
from app.application.use_cases.process_payment import ProcessPaymentUseCase
from app.core.settings import settings
from app.infrastructure.payment_gateway.http import HttpPaymentGateway
from app.infrastructure.queue.consumer import PaymentQueue
from app.infrastructure.queue.producer import PaymentQueueProducer
from app.infrastructure.repositories.payment import InMemoryPaymentRepository
from app.infrastructure.repositories.transaction import InMemoryTransactionRepository
from app.infrastructure.repositories.user import InMemoryUserRepository
from app.workers.payment_worker import PaymentWorker


@lru_cache
def get_user_repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@lru_cache
def get_payment_repo() -> InMemoryPaymentRepository:
    return InMemoryPaymentRepository()


@lru_cache
def get_transaction_repo() -> InMemoryTransactionRepository:
    return InMemoryTransactionRepository()


@lru_cache
def get_queue() -> PaymentQueue:
    return PaymentQueue(maxsize=settings.payment_queue_maxsize)


def get_queue_producer() -> PaymentQueueProducer:
    return PaymentQueueProducer(get_queue())


@lru_cache
def get_gateway() -> HttpPaymentGateway:
    return HttpPaymentGateway(settings.payment_gateway_url, settings.payment_gateway_timeout_s)


def get_create_payment_use_case() -> CreatePaymentUseCase:
    return CreatePaymentUseCase(get_payment_repo(), get_user_repo())


def get_payment_status_use_case() -> GetPaymentStatusUseCase:
    return GetPaymentStatusUseCase(get_payment_repo())


def get_process_payment_use_case() -> ProcessPaymentUseCase:
    return ProcessPaymentUseCase(
        payment_repo=get_payment_repo(),
        user_repo=get_user_repo(),
        transaction_repo=get_transaction_repo(),
        gateway=get_gateway(),
        commission_rate=Decimal(str(settings.commission_rate)),
        max_attempts=settings.gateway_max_attempts,
        backoff_base=settings.gateway_backoff_base,
    )


@lru_cache
def get_worker() -> PaymentWorker:
    return PaymentWorker(get_queue(), get_process_payment_use_case().execute)


async def lifespan() -> AsyncIterator[None]:
    worker = get_worker()
    await worker.start()
    try:
        yield
    finally:
        await worker.stop()
