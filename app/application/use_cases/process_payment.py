from decimal import Decimal
from uuid import UUID, uuid4

from app.application.interfaces.gateway import PaymentGateway
from app.application.interfaces.repositories import (
    PaymentRepository,
    TransactionRepository,
    UserRepository,
)
from app.application.services.retry_service import retry_with_backoff
from app.domain.entities.transaction import Transaction
from app.domain.enums.payment_direction import PaymentDirection
from app.domain.enums.payment_status import PaymentStatus
from app.domain.exceptions import GatewayError


class ProcessPaymentUseCase:
    def __init__(
        self,
        *,
        payment_repo: PaymentRepository,
        user_repo: UserRepository,
        transaction_repo: TransactionRepository,
        gateway: PaymentGateway,
        commission_rate: Decimal,
        max_attempts: int,
        backoff_base: float,
    ) -> None:
        self._payment_repo = payment_repo
        self._user_repo = user_repo
        self._transaction_repo = transaction_repo
        self._gateway = gateway
        self._commission_rate = commission_rate
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base

    async def execute(self, payment_id: UUID) -> None:
        payment = await self._payment_repo.get(payment_id)
        if payment is None:
            return
        payment.status = PaymentStatus.processing
        await self._payment_repo.update(payment)

        async def attempt_charge() -> None:
            payment.attempts += 1
            await self._payment_repo.update(payment)
            await self._gateway.charge(payment.id, payment.user_id, payment.amount)

        try:
            await retry_with_backoff(
                attempt_charge,
                max_attempts=self._max_attempts,
                base_delay=self._backoff_base,
            )
        except Exception as exc:  # noqa: BLE001
            payment.status = PaymentStatus.failed
            await self._payment_repo.update(payment)
            raise GatewayError("Gateway processing failed") from exc

        commission = (payment.amount * self._commission_rate).quantize(Decimal("0.01"))
        payment.commission = commission
        user = await self._user_repo.get(payment.user_id)
        if user is None:
            payment.status = PaymentStatus.failed
            await self._payment_repo.update(payment)
            return
        if payment.direction == PaymentDirection.debit:
            user.balance -= payment.amount + commission
        else:
            user.balance += payment.amount - commission
        await self._user_repo.update(user)

        await self._transaction_repo.add(
            Transaction(
                id=uuid4(),
                payment_id=payment.id,
                user_id=payment.user_id,
                amount=payment.amount,
                category="payment",
            )
        )
        await self._transaction_repo.add(
            Transaction(
                id=uuid4(),
                payment_id=payment.id,
                user_id=payment.user_id,
                amount=commission,
                category="commission",
            )
        )
        payment.status = PaymentStatus.succeeded
        await self._payment_repo.update(payment)
