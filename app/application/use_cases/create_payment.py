from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.application.dto.payment import PaymentCreateRequest, PaymentResponse
from app.application.interfaces.repositories import PaymentRepository, UserRepository
from app.domain.entities.payment import Payment
from app.domain.enums.payment_status import PaymentStatus
from app.domain.exceptions import NotFoundError


class CreatePaymentUseCase:
    def __init__(self, payment_repo: PaymentRepository, user_repo: UserRepository) -> None:
        self._payment_repo = payment_repo
        self._user_repo = user_repo

    async def execute(self, payload: PaymentCreateRequest) -> PaymentResponse:
        user = await self._user_repo.get(payload.user_id)
        if user is None:
            raise NotFoundError("User not found")
        payment = Payment(
            id=uuid4(),
            user_id=payload.user_id,
            amount=Decimal(payload.amount),
            direction=payload.direction,
            status=PaymentStatus.pending,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        await self._payment_repo.create(payment)
        return PaymentResponse(
            id=payment.id,
            user_id=payment.user_id,
            amount=payment.amount,
            direction=payment.direction,
            status=payment.status,
            commission=payment.commission,
        )
