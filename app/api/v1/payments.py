from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path

from app.api.v1.schemas.payment import (
    DepositRequestSchema,
    PaymentCreateResponse,
    PaymentStatusResponse,
    WithdrawRequestSchema,
)
from app.application.dto.payment import DepositDTO, WithdrawDTO
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.core.dependencies import (
    get_deposit_use_case,
    get_payment_repo,
    get_transaction_repo,
    get_withdraw_use_case,
)
from app.core.metrics import metrics
from app.infrastructure.repositories.payment import PaymentRepository
from app.infrastructure.repositories.transaction import TransactionRepository

router = APIRouter(prefix="/payments", tags=["Payments"])
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=64)]
PaymentId = Annotated[int, Path(gt=0)]


async def accepted(payment_id: int, repo: PaymentRepository, amount: Decimal, kind: str) -> dict:
    payment = await repo.get_by_id(payment_id)
    return {
        "payment_id": payment_id,
        "user_id": payment.user_id,
        "status": payment.status.value,
        kind: amount,
    }


@router.post("/deposit", response_model=PaymentCreateResponse, status_code=202)
async def payments_deposit(
    data: DepositRequestSchema,
    use_case: Annotated[DepositBalanceUseCase, Depends(get_deposit_use_case)],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repo)],
    idempotency_key: IdempotencyHeader,
):
    await metrics.inc("payments_deposit_requests_total")
    payment_id = await use_case.execute(
        DepositDTO(user_id=data.user_id, amount=data.deposit, idempotency_key=idempotency_key)
    )
    return await accepted(payment_id, payment_repo, data.deposit, "deposit")


@router.post("/withdraw", response_model=PaymentCreateResponse, status_code=202)
async def payments_withdraw(
    data: WithdrawRequestSchema,
    use_case: Annotated[WithdrawBalanceUseCase, Depends(get_withdraw_use_case)],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repo)],
    idempotency_key: IdempotencyHeader,
):
    await metrics.inc("payments_withdraw_requests_total")
    payment_id = await use_case.execute(
        WithdrawDTO(user_id=data.user_id, amount=data.amount, idempotency_key=idempotency_key)
    )
    return await accepted(payment_id, payment_repo, data.amount, "withdraw")


@router.get("/{payment_id}", response_model=PaymentStatusResponse)
async def payment_status(
    payment_id: PaymentId,
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repo)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repo)],
):
    payment = await payment_repo.get_by_id(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    transaction = await transaction_repo.get_by_payment_id(payment_id)
    return {
        "payment_id": payment.id,
        "user_id": payment.user_id,
        "amount": payment.amount,
        "commission": payment.commission,
        "status": payment.status.value,
        "attempts": payment.attempts,
        "last_error": payment.last_error,
        "transaction_status": transaction.status.value if transaction else None,
    }
