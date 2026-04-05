"""Atomic payment acceptance, reservations and semantic idempotency."""

import logging

from app.application.dto.payment import DepositDTO
from app.core.metrics import metrics
from app.core.settings import settings
from app.domain.exceptions import (
    IdempotencyConflictError,
    UserInsufficientFundsError,
    UserNotFoundError,
)
from app.domain.money import commission_for, idempotency_key, money
from app.infrastructure.db.models.outbox import OutboxEvent
from app.infrastructure.db.models.payment import PaymentStatus
from app.infrastructure.db.models.transaction import TransactionStatus

logger = logging.getLogger("usecase.payment")


class PaymentCommand:
    operation: str

    def __init__(self, user_repo, payment_repo, transaction_repo, session):
        self.user_repo = user_repo
        self.payment_repo = payment_repo
        self.transaction_repo = transaction_repo
        self.session = session

    async def execute(self, dto: DepositDTO) -> int:
        amount = money(dto.amount, positive=True)
        key = idempotency_key(dto.idempotency_key)
        insufficient = False
        # This lock serializes requests for one wallet, including idempotency lookup.
        # Independent users continue concurrently. A DB uniqueness constraint remains
        # the final guard against clients outside this command path.
        async with self.session.begin():
            user = await self.user_repo.get_for_update(dto.user_id)
            if user is None:
                raise UserNotFoundError(f"User {dto.user_id} not found")
            existing = await self.payment_repo.get_by_idempotency_key(user_id=user.id, key=key)
            if existing is not None:
                if existing.operation != self.operation or existing.amount != amount:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used for a different payment"
                    )
                await metrics.inc("idempotency_hits_total")
                payment_id = existing.id
                insufficient = (
                    existing.status == PaymentStatus.FAILED
                    and existing.last_error == "insufficient_funds"
                )
            else:
                fee = commission_for(amount, settings.transaction_fee)
                dto.commission = fee
                reserve = self.operation == "withdraw"
                total = money(amount + fee) if reserve else amount
                insufficient = reserve and user.balance - user.reserved_balance < total
                payment = await self.payment_repo.create(
                    user_id=user.id,
                    amount=amount,
                    commission=fee,
                    status=PaymentStatus.FAILED if insufficient else PaymentStatus.NEW,
                    idempotency_key=key,
                    operation=self.operation,
                    funds_reserved=reserve and not insufficient,
                )
                if insufficient:
                    payment.last_error = "insufficient_funds"
                elif reserve:
                    user.reserved_balance += total
                await self.session.flush()
                await self.transaction_repo.create(
                    user_id=user.id,
                    payment_id=payment.id,
                    amount=amount,
                    commission=fee,
                    type=self.operation,
                    status=(
                        TransactionStatus.FAILED.value
                        if insufficient
                        else TransactionStatus.PROCESSING.value
                    ),
                )
                payment_id = payment.id
                if not insufficient:
                    self.session.add(OutboxEvent(payment_id=payment_id))
                logger.info(
                    "payment accepted: payment_id=%s user_id=%s operation=%s accepted=%s",
                    payment_id,
                    user.id,
                    self.operation,
                    not insufficient,
                )
        # Raise only after committing the failed attempt, so replays are stable.
        if insufficient:
            raise UserInsufficientFundsError(
                f"Insufficient available funds. payment_id={payment_id}"
            )
        return payment_id
