from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.infrastructure.db.models.payment import PaymentStatus
from app.infrastructure.db.models.transaction import TransactionStatus
from app.infrastructure.payment_gateway.http import GatewayResponse
from app.workers.payment_processor import PaymentProcessor, retry_delay


def payment(operation="withdraw", *, reserved=True):
    return SimpleNamespace(
        id=7,
        operation=operation,
        amount=Decimal("1.00"),
        commission=Decimal("0.02"),
        funds_reserved=reserved,
        status=PaymentStatus.PROCESSING,
        last_error=None,
        locked_at=None,
        next_retry_at=None,
    )


@pytest.mark.asyncio
async def test_successful_withdrawal_consumes_exact_hold_and_balance():
    account = SimpleNamespace(balance=Decimal("1.02"), reserved_balance=Decimal("1.02"))
    entry = SimpleNamespace(status=TransactionStatus.PROCESSING)
    event = SimpleNamespace()
    command = payment()
    result = await PaymentProcessor()._settle(command, entry, account, event, datetime.now(UTC))
    assert result == "success"
    assert account.balance == account.reserved_balance == Decimal("0.00")
    assert not command.funds_reserved
    assert entry.status == TransactionStatus.SUCCESS


@pytest.mark.asyncio
async def test_provider_success_with_invalid_hold_retains_account_for_reconciliation():
    account = SimpleNamespace(balance=Decimal("1.02"), reserved_balance=Decimal("0.00"))
    entry = SimpleNamespace(status=TransactionStatus.PROCESSING)
    event = SimpleNamespace()
    command = payment()
    result = await PaymentProcessor()._settle(command, entry, account, event, datetime.now(UTC))
    assert result == "reconciliation"
    assert account.balance == Decimal("1.02")
    assert command.funds_reserved
    assert command.status == PaymentStatus.PROCESSING
    assert command.last_error.startswith("reconciliation_required:")


@pytest.mark.asyncio
async def test_deposit_overflow_after_external_success_requires_reconciliation():
    account = SimpleNamespace(balance=Decimal("9999999999.99"), reserved_balance=Decimal("0.00"))
    entry = SimpleNamespace(status=TransactionStatus.PROCESSING)
    event = SimpleNamespace()
    command = payment("deposit", reserved=False)
    result = await PaymentProcessor()._settle(command, entry, account, event, datetime.now(UTC))
    assert result == "reconciliation"
    assert account.balance == Decimal("9999999999.99")
    assert command.status == PaymentStatus.PROCESSING


def test_retry_backoff_caps_before_bounded_jitter(monkeypatch):
    monkeypatch.setattr(
        "app.workers.payment_processor.random.uniform", lambda minimum, maximum: maximum
    )
    from app.core.settings import settings

    assert (
        retry_delay(1)
        == settings.gateway_backoff_base_seconds + settings.gateway_backoff_jitter_seconds
    )
    assert (
        retry_delay(30)
        == settings.gateway_backoff_max_seconds + settings.gateway_backoff_jitter_seconds
    )


class StoredObjectsSession:
    """Small session double for testing failure policy independently of I/O."""

    def __init__(self, command, event, account):
        self.command, self.event, self.account = command, event, account
        self.scalars = iter([event, SimpleNamespace(status=TransactionStatus.PROCESSING)])

    def begin(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def scalar(self, statement):
        return next(self.scalars)

    async def get(self, model, identifier, **kwargs):
        from app.infrastructure.db.models.user import UserModel

        return self.account if model is UserModel else self.command


@pytest.mark.asyncio
async def test_timeout_then_auth_failure_cannot_release_funds():
    command = payment()
    command.user_id = 9
    command.attempts = 2
    account = SimpleNamespace(balance=Decimal("1.02"), reserved_balance=Decimal("1.02"))
    event = SimpleNamespace(lease_token="current", completed_at=None, outcome_uncertain=True)
    session = StoredObjectsSession(command, event, account)
    processor = PaymentProcessor(session_factory=lambda: session)
    state = await processor._finish(7, "current", GatewayResponse(False, "gateway_error_401", 401))
    assert state == "reconciliation"
    assert account.reserved_balance == Decimal("1.02")
    assert command.funds_reserved
    assert command.status == PaymentStatus.PROCESSING


@pytest.mark.asyncio
async def test_reclaimed_worker_lease_preserves_unknown_external_outcome():
    command = payment()
    command.user_id = 9
    command.attempts = 1
    event = SimpleNamespace(
        completed_at=None,
        lease_token="dead-worker",
        outcome_uncertain=False,
        lease_until=datetime.now(UTC) - timedelta(seconds=1),
    )
    session = StoredObjectsSession(command, event, None)
    processor = PaymentProcessor(session_factory=lambda: session)
    token, payload = await processor._claim(7)
    assert token != "dead-worker"
    assert payload["payment_id"] == 7
    assert event.outcome_uncertain is True


def test_celery_control_reply_and_event_queues_work_without_deprecated_rabbitmq_feature():
    from celery.events.receiver import EventReceiver

    from app.workers.celery_app import celery_app

    mailbox = celery_app.control.mailbox
    control = mailbox.get_queue("isolated-worker")
    reply = mailbox.get_reply_queue()
    events = EventReceiver(None, app=celery_app).queue
    for queue in (control, reply, events):
        assert queue.exclusive and not queue.durable
        assert queue.auto_delete
    assert celery_app.amqp.queues["payments"].durable
