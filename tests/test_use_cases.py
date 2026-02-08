import asyncio
from dataclasses import dataclass

import pytest

from app.application.dto.payment import DepositDTO, WithdrawDTO
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.domain.entities.user import User
from app.domain.exceptions import UserInsufficientFundsError
from app.infrastructure.db.models.payment import PaymentStatus


class FakeSession:
    def begin(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def flush(self):
        return None

    async def rollback(self):
        return None


@dataclass
class FakePayment:
    id: int
    user_id: int
    amount: float
    commission: float
    status: PaymentStatus
    idempotency_key: str | None = None
    last_error: str | None = None


class FakeUserRepo:
    def __init__(self, users: dict[int, User]):
        self.users = users

    async def get_by_id(self, user_id: int):
        return self.users.get(user_id)

    async def save(self, user: User) -> None:
        self.users[user.id] = user


class FakePaymentRepo:
    def __init__(self):
        self._payments: list[FakePayment] = []
        self._id = 1

    async def create(self, user_id: int, amount: float, commission: float, status: PaymentStatus, idempotency_key=None):
        payment = FakePayment(
            id=self._id,
            user_id=user_id,
            amount=amount,
            commission=commission,
            status=status,
            idempotency_key=idempotency_key,
        )
        self._id += 1
        self._payments.append(payment)
        return payment

    async def get_by_idempotency_key(self, user_id: int, key: str):
        for p in self._payments:
            if p.user_id == user_id and p.idempotency_key == key:
                return p
        return None


class FakeTransactionRepo:
    def __init__(self):
        self.items = []

    async def create(self, **kwargs):
        self.items.append(kwargs)
        return kwargs


class FakeTaskRepo:
    def __init__(self, session):
        self.session = session
        if not hasattr(session, "_tasks"):
            session._tasks = []

    async def create(self, payment_id: int):
        self.session._tasks.append(payment_id)


@pytest.mark.asyncio
async def test_deposit_creates_payment_transaction_and_task(monkeypatch):
    session = FakeSession()
    users = {1: User(id=1, balance=0)}
    user_repo = FakeUserRepo(users)
    payment_repo = FakePaymentRepo()
    transaction_repo = FakeTransactionRepo()

    monkeypatch.setattr("app.application.use_cases.deposit_balance.PaymentTaskRepository", FakeTaskRepo)

    use_case = DepositBalanceUseCase(user_repo, payment_repo, transaction_repo, session)
    payment_id = await use_case.execute(DepositDTO(user_id=1, amount=100, idempotency_key="k1"))

    assert payment_id == 1
    assert len(payment_repo._payments) == 1
    assert len(transaction_repo.items) == 1
    assert session._tasks == [1]


@pytest.mark.asyncio
async def test_deposit_idempotency_returns_existing(monkeypatch):
    session = FakeSession()
    users = {1: User(id=1, balance=0)}
    user_repo = FakeUserRepo(users)
    payment_repo = FakePaymentRepo()
    transaction_repo = FakeTransactionRepo()

    monkeypatch.setattr("app.application.use_cases.deposit_balance.PaymentTaskRepository", FakeTaskRepo)

    use_case = DepositBalanceUseCase(user_repo, payment_repo, transaction_repo, session)
    first_id = await use_case.execute(DepositDTO(user_id=1, amount=100, idempotency_key="k1"))
    second_id = await use_case.execute(DepositDTO(user_id=1, amount=100, idempotency_key="k1"))

    assert first_id == second_id
    assert len(payment_repo._payments) == 1
    assert session._tasks == [1]


@pytest.mark.asyncio
async def test_withdraw_insufficient_funds_creates_failed_payment(monkeypatch):
    session = FakeSession()
    users = {1: User(id=1, balance=0)}
    user_repo = FakeUserRepo(users)
    payment_repo = FakePaymentRepo()
    transaction_repo = FakeTransactionRepo()

    monkeypatch.setattr("app.application.use_cases.withdraw_balance.PaymentTaskRepository", FakeTaskRepo)

    use_case = WithdrawBalanceUseCase(user_repo, payment_repo, transaction_repo, session)

    with pytest.raises(UserInsufficientFundsError):
        await use_case.execute(WithdrawDTO(user_id=1, amount=10, idempotency_key="k2"))

    assert len(payment_repo._payments) == 1
    assert payment_repo._payments[0].status == PaymentStatus.FAILED
    assert len(transaction_repo.items) == 1
    assert not hasattr(session, "_tasks")


@pytest.mark.asyncio
async def test_withdraw_success_enqueues_task(monkeypatch):
    session = FakeSession()
    users = {1: User(id=1, balance=100)}
    user_repo = FakeUserRepo(users)
    payment_repo = FakePaymentRepo()
    transaction_repo = FakeTransactionRepo()

    monkeypatch.setattr("app.application.use_cases.withdraw_balance.PaymentTaskRepository", FakeTaskRepo)

    use_case = WithdrawBalanceUseCase(user_repo, payment_repo, transaction_repo, session)
    payment_id = await use_case.execute(WithdrawDTO(user_id=1, amount=10, idempotency_key="k3"))

    assert payment_id == 1
    assert len(payment_repo._payments) == 1
    assert session._tasks == [1]
