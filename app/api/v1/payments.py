from fastapi import APIRouter, HTTPException, Header
from app.infrastructure.db.session import session_depends
from app.application.dto.payment import DepositDTO
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.infrastructure.repositories.user import UserRepository
from app.infrastructure.repositories.payment import PaymentRepository
from app.infrastructure.repositories.transaction import TransactionRepository
from app.application.dto.payment import WithdrawDTO
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.api.v1.schemas.payment import DepositRequestSchema, WithdrawRequestSchema
from app.core.metrics import metrics

router = APIRouter(prefix="/payments", tags=["Payments"])

# ------------------ Endpoint ------------------
@router.post("/deposit")
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
        payment_id: int = await use_case.execute(
            DepositDTO(user_id=data.user_id, amount=data.deposit, idempotency_key=idempotency_key)
        )
        return {
            "payment_id": payment_id,
            "user_id": data.user_id,
            "deposit": data.deposit,
            "status": "processing"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/withdraw")
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
        payment_id: int = await use_case.execute(
            WithdrawDTO(user_id=data.user_id, amount=data.amount, idempotency_key=idempotency_key)
        )
        return {
            "payment_id": payment_id,
            "user_id": data.user_id,
            "withdraw": data.amount,
            "status": "processing"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}")
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
