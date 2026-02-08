from app.application.dto.payment import PaymentStatusResponse
from app.application.interfaces.repositories import PaymentRepository
from app.domain.exceptions import NotFoundError


class GetPaymentStatusUseCase:
    def __init__(self, payment_repo: PaymentRepository) -> None:
        self._payment_repo = payment_repo

    async def execute(self, payment_id) -> PaymentStatusResponse:
        payment = await self._payment_repo.get(payment_id)
        if payment is None:
            raise NotFoundError("Payment not found")
        return PaymentStatusResponse(
            id=payment.id,
            status=payment.status,
            attempts=payment.attempts,
            commission=payment.commission,
        )
