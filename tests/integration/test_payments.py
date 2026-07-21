import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.application.dto.payment import DepositDTO, WithdrawDTO
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.core.settings import settings
from app.domain.exceptions import IdempotencyConflictError, UserInsufficientFundsError
from app.infrastructure.db.models.outbox import OutboxEvent, PaymentResolution
from app.infrastructure.db.models.payment import PaymentModel
from app.infrastructure.db.models.payment_dlq import PaymentDLQModel
from app.infrastructure.db.models.user import UserModel
from app.infrastructure.payment_gateway.http import GatewayResponse, PaymentGatewayClient
from app.infrastructure.repositories.payment import PaymentRepository
from app.infrastructure.repositories.transaction import TransactionRepository
from app.infrastructure.repositories.user import UserRepository
from app.workers.outbox import publish_batch
from app.workers.payment_processor import PaymentProcessor

pytestmark = pytest.mark.integration


async def account(sessions, balance="0.00"):
    async with sessions() as session, session.begin():
        user = UserModel(balance=Decimal(balance), reserved_balance=Decimal("0.00"))
        session.add(user)
        await session.flush()
        return user.id


async def command(sessions, user_id, amount="1.00", key="key", operation="deposit"):
    async with sessions() as session:
        cls, dto = (
            (DepositBalanceUseCase, DepositDTO)
            if operation == "deposit"
            else (WithdrawBalanceUseCase, WithdrawDTO)
        )
        return await cls(
            UserRepository(session),
            PaymentRepository(session),
            TransactionRepository(session),
            session,
        ).execute(dto(user_id=user_id, amount=Decimal(amount), idempotency_key=key))


async def balances(sessions, user_id):
    async with sessions() as session:
        user = await session.get(UserModel, user_id)
        return user.balance, user.reserved_balance


async def due(sessions, payment_id, expire=False):
    async with sessions() as session, session.begin():
        payment = await session.get(PaymentModel, payment_id)
        payment.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
        event = await session.scalar(
            select(OutboxEvent).where(OutboxEvent.payment_id == payment_id)
        )
        event.available_at = datetime.now(UTC) - timedelta(seconds=1)
        if expire:
            event.lease_until = datetime.now(UTC) - timedelta(seconds=1)


class Gateway:
    def __init__(self, *responses):
        self.responses = list(responses) or [GatewayResponse(True)]
        self.calls = []

    async def charge(self, payload):
        self.calls.append(payload)
        return self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]


async def test_concurrent_replay_creates_one_payment_and_one_outbox(sessions):
    user_id = await account(sessions)
    ids = await asyncio.gather(*(command(sessions, user_id, key="same") for _ in range(20)))
    assert len(set(ids)) == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentModel)) == 1
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 1


async def test_idempotency_conflicts_on_amount_or_operation(sessions):
    user_id = await account(sessions, "100")
    await command(sessions, user_id, key="same")
    with pytest.raises(IdempotencyConflictError):
        await command(sessions, user_id, amount="2.00", key="same")
    with pytest.raises(IdempotencyConflictError):
        await command(sessions, user_id, key="same", operation="withdraw")


async def test_parallel_withdrawals_cannot_reserve_more_than_balance(sessions):
    user_id = await account(sessions, "102.00")
    outcomes = await asyncio.gather(
        *(
            command(sessions, user_id, amount="10.00", key=f"w-{i}", operation="withdraw")
            for i in range(16)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(value, int) for value in outcomes) == 10
    assert sum(isinstance(value, UserInsufficientFundsError) for value in outcomes) == 6
    assert await balances(sessions, user_id) == (Decimal("102.00"), Decimal("102.00"))


async def test_exact_balance_withdrawal_and_redelivery_settle_once(sessions):
    user_id = await account(sessions, "1.02")
    payment_id = await command(sessions, user_id, key="w", operation="withdraw")
    gateway = Gateway()
    worker = PaymentProcessor(session_factory=sessions, gateway=gateway)
    states = await asyncio.gather(*(worker.process(payment_id) for _ in range(12)))
    assert "success" in states
    assert len(gateway.calls) == 1
    assert await balances(sessions, user_id) == (Decimal("0.00"), Decimal("0.00"))


async def test_deposit_redelivery_credits_exact_net_amount_once(sessions):
    user_id = await account(sessions)
    payment_id = await command(sessions, user_id, amount="100.00")
    worker = PaymentProcessor(session_factory=sessions, gateway=Gateway())
    await asyncio.gather(*(worker.process(payment_id) for _ in range(10)))
    assert await balances(sessions, user_id) == (Decimal("98.00"), Decimal("0.00"))


async def test_definitive_decline_releases_hold_and_records_dlq(sessions):
    user_id = await account(sessions, "1.02")
    payment_id = await command(sessions, user_id, operation="withdraw")
    worker = PaymentProcessor(
        session_factory=sessions, gateway=Gateway(GatewayResponse(False, "declined"))
    )
    assert await worker.process(payment_id) == "failed"
    assert await worker.process(payment_id) == "failed"
    assert await balances(sessions, user_id) == (Decimal("1.02"), Decimal("0.00"))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentDLQModel)) == 1


async def test_unknown_outcome_retains_hold_until_audited_resolution(sessions, monkeypatch):
    monkeypatch.setattr(settings, "gateway_max_attempts", 1)
    user_id = await account(sessions, "1.02")
    payment_id = await command(sessions, user_id, operation="withdraw")
    worker = PaymentProcessor(
        session_factory=sessions,
        gateway=Gateway(GatewayResponse(False, "timeout", retryable=True, uncertain=True)),
    )
    assert await worker.process(payment_id) == "reconciliation"
    assert await balances(sessions, user_id) == (Decimal("1.02"), Decimal("1.02"))
    assert await worker.process(payment_id) == "reconciliation"
    assert await worker.resolve(payment_id, "success", "provider-receipt-123") == "success"
    assert await balances(sessions, user_id) == (Decimal("0"), Decimal("0"))
    with pytest.raises(ValueError, match="finalized"):
        await worker.resolve(payment_id, "success", "provider-receipt-123")
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentResolution)) == 1


async def test_timeout_then_unauthorized_never_releases_an_ambiguous_hold(sessions):
    user_id = await account(sessions, "1.02")
    payment_id = await command(sessions, user_id, operation="withdraw")
    gateway = Gateway(
        GatewayResponse(False, "timeout", retryable=True, uncertain=True),
        GatewayResponse(False, "unauthorized"),
    )
    worker = PaymentProcessor(session_factory=sessions, gateway=gateway)
    assert await worker.process(payment_id) == "retry"
    await due(sessions, payment_id)
    assert await worker.process(payment_id) == "reconciliation"
    assert await balances(sessions, user_id) == (Decimal("1.02"), Decimal("1.02"))


async def test_crashed_processor_is_recoverable_after_lease_expiry(sessions):
    user_id = await account(sessions)
    payment_id = await command(sessions, user_id)

    class CrashedGateway:
        async def charge(self, payload):
            raise RuntimeError("simulated process interruption")

    with pytest.raises(RuntimeError):
        await PaymentProcessor(session_factory=sessions, gateway=CrashedGateway()).process(
            payment_id
        )
    await due(sessions, payment_id, expire=True)
    assert (
        await PaymentProcessor(session_factory=sessions, gateway=Gateway()).process(payment_id)
        == "success"
    )
    assert await balances(sessions, user_id) == (Decimal("0.98"), Decimal("0"))


async def test_late_completion_is_fenced_after_another_worker_recovers(sessions):
    user_id = await account(sessions)
    payment_id = await command(sessions, user_id)
    entered, resume = asyncio.Event(), asyncio.Event()

    class Delayed:
        async def charge(self, payload):
            entered.set()
            await resume.wait()
            return GatewayResponse(True)

    original = asyncio.create_task(
        PaymentProcessor(session_factory=sessions, gateway=Delayed()).process(payment_id)
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await due(sessions, payment_id, expire=True)
        assert (
            await PaymentProcessor(session_factory=sessions, gateway=Gateway()).process(payment_id)
            == "success"
        )
        resume.set()
        assert await original == "superseded"
        assert await balances(sessions, user_id) == (Decimal("0.98"), Decimal("0"))
    finally:
        resume.set()
        await original


async def test_broker_outage_preserves_outbox_and_can_publish_later(sessions):
    user_id = await account(sessions)
    payment_id = await command(sessions, user_id)

    def unavailable(_):
        raise ConnectionError("broker down")

    assert await publish_batch(session_factory=sessions, publish=unavailable) == 0
    async with sessions() as session:
        event = await session.scalar(select(OutboxEvent))
        assert event.last_error == "broker_publish_failed"
        assert event.completed_at is None
    await due(sessions, payment_id)
    published = []
    assert await publish_batch(session_factory=sessions, publish=published.append) == 1
    assert published == [payment_id]


async def test_database_error_rolls_back_reservation_payment_and_outbox(sessions):
    user_id = await account(sessions, "1.02")

    class BrokenTransactions:
        async def create(self, **kwargs):
            raise RuntimeError("simulate transaction write failure")

    async with sessions() as session:
        worker = WithdrawBalanceUseCase(
            UserRepository(session), PaymentRepository(session), BrokenTransactions(), session
        )
        with pytest.raises(RuntimeError):
            await worker.execute(
                WithdrawDTO(user_id=user_id, amount=Decimal("1"), idempotency_key="atomic")
            )
    assert await balances(sessions, user_id) == (Decimal("1.02"), Decimal("0"))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentModel)) == 0
        assert await session.scalar(select(func.count()).select_from(OutboxEvent)) == 0


async def test_real_mock_gateway_persists_idempotency_receipts(sessions):
    from app.infrastructure.db.session import get_session
    from app.mock_gateway_app import app as gateway_app

    async def override_session():
        async with sessions() as session:
            yield session

    gateway_app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=gateway_app), base_url="http://mock"
        ) as client:
            gateway = PaymentGatewayClient("http://mock/mock-gateway", client=client)
            payload = {
                "payment_id": 1,
                "user_id": 1,
                "amount": "1.00",
                "commission": "0.02",
                "type": "deposit",
            }
            assert (await gateway.charge(payload)).success
            assert (await gateway.charge({**payload, "amount": "1"})).success
            conflict = await gateway.charge({**payload, "amount": "2.00"})
            assert conflict.uncertain and not conflict.success
    finally:
        gateway_app.dependency_overrides.clear()


async def test_failed_manual_resolution_releases_hold_and_audits_once(sessions, monkeypatch):
    monkeypatch.setattr(settings, "gateway_max_attempts", 1)
    user_id = await account(sessions, "1.02")
    payment_id = await command(sessions, user_id, operation="withdraw")
    worker = PaymentProcessor(
        session_factory=sessions,
        gateway=Gateway(GatewayResponse(False, "timeout", retryable=True, uncertain=True)),
    )
    assert await worker.process(payment_id) == "reconciliation"
    assert await worker.resolve(payment_id, "failed", "provider-verification-no-charge") == "failed"
    assert await balances(sessions, user_id) == (Decimal("1.02"), Decimal("0"))
    with pytest.raises(ValueError, match="finalized"):
        await worker.resolve(payment_id, "failed", "provider-verification-no-charge")
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PaymentResolution)) == 1


async def test_lost_publish_confirmation_can_redeliver_without_duplicate_settlement(sessions):
    user_id = await account(sessions)
    payment_id = await command(sessions, user_id)
    messages = []

    def confirm_lost(value):
        messages.append(value)
        raise ConnectionError("message delivered but publisher confirmation lost")

    assert await publish_batch(session_factory=sessions, publish=confirm_lost) == 0
    await due(sessions, payment_id)
    assert await publish_batch(session_factory=sessions, publish=messages.append) == 1
    assert messages == [payment_id, payment_id]
    gateway = Gateway()
    worker = PaymentProcessor(session_factory=sessions, gateway=gateway)
    await asyncio.gather(*(worker.process(value) for value in messages))
    assert len(gateway.calls) == 1
    assert await balances(sessions, user_id) == (Decimal("0.98"), Decimal("0"))


async def test_api_lifecycle_replay_and_persisted_metrics(sessions, monkeypatch):
    from app.infrastructure.db.session import get_session
    from app.main import app

    async def override_session():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr("app.api.v1.metrics.AsyncSessionLocal", sessions)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"X-API-Key": settings.api_key.get_secret_value()},
        ) as client:
            response = await client.post("/api/v1/users/", json={"balance": "1.02"})
            assert response.status_code == 200
            user_id = response.json()["id"]
            response = await client.post(
                "/api/v1/payments/withdraw",
                json={"user_id": user_id, "amount": "1.00"},
                headers={"Idempotency-Key": "api-lifecycle"},
            )
            assert response.status_code == 202
            payment_id = response.json()["payment_id"]
            assert (
                await PaymentProcessor(session_factory=sessions, gateway=Gateway()).process(
                    payment_id
                )
                == "success"
            )
            replay = await client.post(
                "/api/v1/payments/withdraw",
                json={"user_id": user_id, "amount": "1"},
                headers={"Idempotency-Key": "api-lifecycle"},
            )
            assert replay.json()["status"] == "success"
            wallet = (await client.get(f"/api/v1/users/{user_id}")).json()
            assert wallet["available_balance"] == "0.00"
            metrics_response = await client.get("/metrics")
            assert metrics_response.status_code == 200
            assert 'payments_state{state="success"} 1.0' in metrics_response.text
    finally:
        app.dependency_overrides.clear()
