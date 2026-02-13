import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException

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

logger = logging.getLogger("payments_api")

router = APIRouter(prefix="/payments", tags=["Payments"])


def _response(payment_id: int, user_id: int, amount: float, kind: str, status: str) -> dict:
    payload = {
        "payment_id": payment_id,
        "user_id": user_id,
        "status": status,
    }
    payload[kind] = amount
    return payload


@router.post(
    "/deposit",
    summary="Пополнение баланса (асинхронно)",
    description="Создаёт платеж на пополнение и ставит задачу в очередь обработки.",
    response_model=PaymentCreateResponse,
)
async def payments_deposit(
    data: DepositRequestSchema,
    use_case: Annotated[DepositBalanceUseCase, Depends(get_deposit_use_case)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    await metrics.inc("payments_deposit_requests_total")
    logger.info("deposit request: user_id=%s amount=%s idempotency=%s", data.user_id, data.deposit, bool(idempotency_key))
    payment_id: int = await use_case.execute(
        DepositDTO(user_id=data.user_id, amount=data.deposit, idempotency_key=idempotency_key)
    )
    logger.info("deposit accepted: payment_id=%s user_id=%s", payment_id, data.user_id)
    return _response(payment_id, data.user_id, data.deposit, "deposit", "processing")


@router.post(
    "/withdraw",
    summary="Списание баланса (асинхронно)",
    description="Создаёт платеж на списание и ставит задачу в очередь обработки.",
    response_model=PaymentCreateResponse,
)
async def payments_withdraw(
    data: WithdrawRequestSchema,
    use_case: Annotated[WithdrawBalanceUseCase, Depends(get_withdraw_use_case)],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    await metrics.inc("payments_withdraw_requests_total")
    logger.info("withdraw request: user_id=%s amount=%s idempotency=%s", data.user_id, data.amount, bool(idempotency_key))
    payment_id: int = await use_case.execute(
        WithdrawDTO(user_id=data.user_id, amount=data.amount, idempotency_key=idempotency_key)
    )
    logger.info("withdraw accepted: payment_id=%s user_id=%s", payment_id, data.user_id)
    return _response(payment_id, data.user_id, data.amount, "withdraw", "processing")


@router.get(
    "/{payment_id}",
    summary="Статус платежа",
    description="Возвращает текущий статус и метаданные платежа.",
    response_model=PaymentStatusResponse,
)
async def payment_status(
    payment_id: int,
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repo)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repo)],
):
    payment = await payment_repo.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    transaction = await transaction_repo.get_by_payment_id(payment_id)

    return {
        "payment_id": payment.id,
        "user_id": payment.user_id,
        "amount": float(payment.amount),
        "commission": float(payment.commission),
        "status": payment.status.value,
        "attempts": payment.attempts,
        "last_error": payment.last_error,
        "transaction_status": transaction.status.value if transaction else None,
    }
