import logging

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy.exc import IntegrityError

from app.application.dto.payment import DepositDTO, WithdrawDTO
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.api.v1.schemas.payment import (
    DepositRequestSchema,
    PaymentCreateResponse,
    PaymentStatusResponse,
    WithdrawRequestSchema,
)
from app.core.metrics import metrics
from app.domain.exceptions import UserInsufficientFundsError, UserNotFoundError
from app.infrastructure.db.session import session_depends
from app.infrastructure.repositories.payment import PaymentRepository
from app.infrastructure.repositories.transaction import TransactionRepository
from app.infrastructure.repositories.user import UserRepository

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
    session: session_depends,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)
    use_case = DepositBalanceUseCase(user_repo, payment_repo, transaction_repo, session)

    try:
        await metrics.inc("payments_deposit_requests_total")
        logger.info("deposit request: user_id=%s amount=%s idempotency=%s", data.user_id, data.deposit, bool(idempotency_key))
        payment_id: int = await use_case.execute(
            DepositDTO(user_id=data.user_id, amount=data.deposit, idempotency_key=idempotency_key)
        )
        logger.info("deposit accepted: payment_id=%s user_id=%s", payment_id, data.user_id)
        return _response(payment_id, data.user_id, data.deposit, "deposit", "processing")
    except UserNotFoundError as e:
        logger.warning("deposit failed: user_not_found user_id=%s", data.user_id)
        raise HTTPException(status_code=404, detail=str(e))
    except IntegrityError:
        await session.rollback()
        if idempotency_key:
            existing = await payment_repo.get_by_idempotency_key(data.user_id, idempotency_key)
            if existing:
                logger.info("deposit idempotency conflict resolved: payment_id=%s", existing.id)
                return _response(existing.id, data.user_id, data.deposit, "deposit", existing.status.value)
        logger.warning("deposit idempotency conflict")
        raise HTTPException(status_code=409, detail="Idempotency conflict")
    except Exception as e:
        logger.exception("deposit failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/withdraw",
    summary="Списание баланса (асинхронно)",
    description="Создаёт платеж на списание и ставит задачу в очередь обработки.",
    response_model=PaymentCreateResponse,
)
async def payments_withdraw(
    data: WithdrawRequestSchema,
    session: session_depends,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)
    use_case = WithdrawBalanceUseCase(user_repo, payment_repo, transaction_repo, session)

    try:
        await metrics.inc("payments_withdraw_requests_total")
        logger.info("withdraw request: user_id=%s amount=%s idempotency=%s", data.user_id, data.amount, bool(idempotency_key))
        payment_id: int = await use_case.execute(
            WithdrawDTO(user_id=data.user_id, amount=data.amount, idempotency_key=idempotency_key)
        )
        logger.info("withdraw accepted: payment_id=%s user_id=%s", payment_id, data.user_id)
        return _response(payment_id, data.user_id, data.amount, "withdraw", "processing")
    except UserNotFoundError as e:
        logger.warning("withdraw failed: user_not_found user_id=%s", data.user_id)
        raise HTTPException(status_code=404, detail=str(e))
    except UserInsufficientFundsError as e:
        logger.warning("withdraw failed: insufficient_funds user_id=%s", data.user_id)
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        await session.rollback()
        if idempotency_key:
            existing = await payment_repo.get_by_idempotency_key(data.user_id, idempotency_key)
            if existing:
                logger.info("withdraw idempotency conflict resolved: payment_id=%s", existing.id)
                return _response(existing.id, data.user_id, data.amount, "withdraw", existing.status.value)
        logger.warning("withdraw idempotency conflict")
        raise HTTPException(status_code=409, detail="Idempotency conflict")
    except Exception as e:
        logger.exception("withdraw failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{payment_id}",
    summary="Статус платежа",
    description="Возвращает текущий статус и метаданные платежа.",
    response_model=PaymentStatusResponse,
)
async def payment_status(
    payment_id: int,
    session: session_depends,
):
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)

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
