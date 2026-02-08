from fastapi import APIRouter, HTTPException
from infrastructure.db.session import session_depends
from application.dto.payment import DepositDTO
from application.use_cases.deposit_balance import DepositBalanceUseCase
from infrastructure.repositories.user import UserRepository
from infrastructure.repositories.payment import PaymentRepository
from infrastructure.repositories.transaction import TransactionRepository
from application.dto.payment import WithdrawDTO
from application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from api.v1.schemas.payment import DepositRequestSchema, WithdrawRequestSchema

router = APIRouter(prefix="/payments", tags=["Payments"])

# ------------------ Endpoint ------------------
@router.post("/deposit")
async def payments_deposit(
    data: DepositRequestSchema,
    session: session_depends
):
    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)
    use_case = DepositBalanceUseCase(user_repo, payment_repo, transaction_repo, session)

    try:
        payment_id = await use_case.execute(
            DepositDTO(user_id=data.user_id, amount=data.deposit)
        )
        return {
            "user_id": data.user_id,
            "deposit": data.deposit,
            "payment_id": payment_id,
            "status": "processing"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/withdraw")
async def payments_withdraw(
    data: WithdrawRequestSchema,
    session: session_depends
):
    user_repo = UserRepository(session)
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)
    use_case = WithdrawBalanceUseCase(user_repo, payment_repo, transaction_repo, session)

    try:
        payment_id = await use_case.execute(
            WithdrawDTO(user_id=data.user_id, amount=data.amount)
        )
        return {
            "user_id": data.user_id,
            "withdraw": data.amount,
            "payment_id": payment_id,
            "status": "processing"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}/status")
async def payment_status(payment_id: int, session: session_depends):
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)
    payment = await payment_repo.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    transaction = await transaction_repo.get_by_payment_id(payment_id)
    return {
        "payment_id": payment.id,
        "status": payment.status.value,
        "transaction_status": transaction.status.value if transaction else None,
        "transaction_type": transaction.type.value if transaction else None,
        "amount": float(payment.amount),
        "commission": float(payment.commission),
    }
