from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.create_user import CreateUserUseCase
from app.application.use_cases.deposit_balance import DepositBalanceUseCase
from app.application.use_cases.withdraw_balance import WithdrawBalanceUseCase
from app.infrastructure.db.session import get_session
from app.infrastructure.repositories.payment import PaymentRepository
from app.infrastructure.repositories.transaction import TransactionRepository
from app.infrastructure.repositories.user import UserRepository


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_user_repo(session: SessionDep) -> UserRepository:
    return UserRepository(session)


async def get_payment_repo(session: SessionDep) -> PaymentRepository:
    return PaymentRepository(session)


async def get_transaction_repo(session: SessionDep) -> TransactionRepository:
    return TransactionRepository(session)


async def get_create_user_use_case(
    session: SessionDep,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> CreateUserUseCase:
    return CreateUserUseCase(session, user_repo)


async def get_deposit_use_case(
    session: SessionDep,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repo)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repo)],
) -> DepositBalanceUseCase:
    return DepositBalanceUseCase(user_repo, payment_repo, transaction_repo, session)


async def get_withdraw_use_case(
    session: SessionDep,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    payment_repo: Annotated[PaymentRepository, Depends(get_payment_repo)],
    transaction_repo: Annotated[TransactionRepository, Depends(get_transaction_repo)],
) -> WithdrawBalanceUseCase:
    return WithdrawBalanceUseCase(user_repo, payment_repo, transaction_repo, session)
