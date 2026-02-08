from fastapi import APIRouter, HTTPException
from decimal import Decimal
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
        new_balance: Decimal = await use_case.execute(
            DepositDTO(user_id=data.user_id, amount=data.deposit)
        )
        return {
            "user_id": data.user_id,
            "deposit": data.deposit,
            "new_balance": float(new_balance),
            "status": "success"
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
        new_balance: Decimal = await use_case.execute(
            WithdrawDTO(user_id=data.user_id, amount=data.amount)
        )
        return {
            "user_id": data.user_id,
            "withdraw": data.amount,
            "new_balance": float(new_balance),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
