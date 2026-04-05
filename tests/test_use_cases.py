from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.dto.payment import DepositDTO, WithdrawDTO
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.domain.entities.user import User
from app.domain.exceptions import (
    IdempotencyConflictError,
    UserInsufficientFundsError,
    UserNotFoundError,
)
from app.infrastructure.db.models.outbox import OutboxEvent
from app.infrastructure.db.models.payment import PaymentStatus


class FakeSession:
    def __init__(self):
        self.added = []
        self.in_transaction = False
        self.committed = 0

    def begin(self):
        return self

    async def __aenter__(self):
        self.in_transaction = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.in_transaction = False
        self.committed += exc_type is None
        return False

    async def flush(self):
        assert self.in_transaction

    def add(self, value):
        assert self.in_transaction, "outbox must be part of the payment transaction"
        self.added.append(value)


class FakeUserRepo:
    def __init__(self, balance):
        self.user = User(id=1, balance=balance)
        self.locked = False

    async def get_for_update(self, user_id):
        self.locked = True
        return self.user if user_id == 1 else None


class FakePaymentRepo:
    def __init__(self):
        self.items = []

    async def create(self, **kwargs):
        value = SimpleNamespace(id=len(self.items) + 1, last_error=None, **kwargs)
        self.items.append(value)
        return value

    async def get_by_idempotency_key(self, user_id, key):
        return next(
            (
                payment
                for payment in self.items
                if payment.user_id == user_id and payment.idempotency_key == key
            ),
            None,
        )


class FakeTransactionRepo:
    def __init__(self):
        self.items = []

    async def create(self, **kwargs):
        self.items.append(kwargs)


@pytest.fixture
def wallet():
    session = FakeSession()
    users = FakeUserRepo("100.00")
    payments = FakePaymentRepo()
    transactions = FakeTransactionRepo()
    return SimpleNamespace(
        session=session,
        users=users,
        payments=payments,
        transactions=transactions,
        deposit=DepositBalanceUseCase(users, payments, transactions, session),
        withdraw=WithdrawBalanceUseCase(users, payments, transactions, session),
    )


@pytest.mark.asyncio
async def test_deposit_atomically_creates_transaction_and_outbox(wallet):
    payment_id = await wallet.deposit.execute(
        DepositDTO(user_id=1, amount="100.00", idempotency_key="deposit-1")
    )
    assert wallet.users.locked
    assert wallet.session.committed == 1
    assert wallet.payments.items[0].commission == Decimal("2.00")
    assert wallet.payments.items[0].operation == "deposit"
    assert len(wallet.transactions.items) == 1
    assert len(wallet.session.added) == 1
    assert isinstance(wallet.session.added[0], OutboxEvent)
    assert wallet.session.added[0].payment_id == payment_id
    assert wallet.users.user.balance == Decimal("100.00")


@pytest.mark.asyncio
async def test_idempotent_withdrawal_does_not_double_reserve_or_enqueue(wallet):
    dto = WithdrawDTO(user_id=1, amount="10.00", idempotency_key="withdraw-1")
    first_id = await wallet.withdraw.execute(dto)
    second_id = await wallet.withdraw.execute(dto)
    assert first_id == second_id
    assert (
        len(wallet.payments.items)
        == len(wallet.transactions.items)
        == len(wallet.session.added)
        == 1
    )
    assert wallet.users.user.reserved_balance == Decimal("10.20")
    assert wallet.users.user.balance == Decimal("100.00")


@pytest.mark.asyncio
async def test_exact_available_balance_can_be_fully_reserved(wallet):
    wallet.users.user.balance = Decimal("1.02")
    await wallet.withdraw.execute(
        WithdrawDTO(user_id=1, amount="1.00", idempotency_key="exact-boundary")
    )
    assert wallet.users.user.reserved_balance == Decimal("1.02")
    assert wallet.payments.items[0].funds_reserved is True


@pytest.mark.asyncio
async def test_other_withdrawal_cannot_spend_reserved_funds(wallet):
    await wallet.withdraw.execute(WithdrawDTO(user_id=1, amount="90.00", idempotency_key="first"))
    with pytest.raises(UserInsufficientFundsError):
        await wallet.withdraw.execute(
            WithdrawDTO(user_id=1, amount="10.00", idempotency_key="second")
        )
    assert wallet.users.user.reserved_balance == Decimal("91.80")
    assert wallet.payments.items[1].status == PaymentStatus.FAILED
    assert wallet.payments.items[1].funds_reserved is False
    assert len(wallet.session.added) == 1
    assert wallet.session.committed == 2


@pytest.mark.asyncio
async def test_insufficient_funds_replay_preserves_original_result_after_balance_change(wallet):
    dto = WithdrawDTO(user_id=1, amount="100.00", idempotency_key="insufficient")
    for new_balance in [Decimal("100.00"), Decimal("1000.00")]:
        wallet.users.user.balance = new_balance
        with pytest.raises(UserInsufficientFundsError, match="payment_id=1"):
            await wallet.withdraw.execute(dto)
    assert len(wallet.payments.items) == len(wallet.transactions.items) == 1
    assert wallet.session.added == []
    assert wallet.session.committed == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["amount", "operation"])
async def test_idempotency_key_cannot_be_reused_for_another_payload(wallet, change):
    await wallet.deposit.execute(DepositDTO(user_id=1, amount="10.00", idempotency_key="same"))
    command = wallet.withdraw if change == "operation" else wallet.deposit
    dto = DepositDTO(
        user_id=1,
        amount="10.00" if change == "operation" else "11.00",
        idempotency_key="same",
    )
    with pytest.raises(IdempotencyConflictError):
        await command.execute(dto)
    assert len(wallet.session.added) == 1
    assert wallet.users.user.reserved_balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_missing_user_creates_no_payment_or_outbox(wallet):
    with pytest.raises(UserNotFoundError):
        await wallet.deposit.execute(
            DepositDTO(user_id=999, amount="1.00", idempotency_key="missing")
        )
    assert wallet.payments.items == []
    assert wallet.session.added == []
    assert wallet.session.committed == 0
