import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.settings import settings
from infrastructure.db.session import AsyncSessionLocal
from infrastructure.payment_gateway.http import HttpPaymentGatewayClient
from infrastructure.repositories.payment import PaymentRepository
from infrastructure.repositories.transaction import TransactionRepository
from infrastructure.repositories.user import UserRepository
from infrastructure.db.models.payment import PaymentStatus
from infrastructure.db.models.transaction import TransactionStatus, TransactionType
from domain.exceptions import UserInsufficientFundsError

logger = logging.getLogger(__name__)


async def process_payment(session: AsyncSession, payment_id: int, gateway: HttpPaymentGatewayClient) -> None:
    payment_repo = PaymentRepository(session)
    transaction_repo = TransactionRepository(session)
    user_repo = UserRepository(session)

    payment = await payment_repo.get_by_id(payment_id)
    if not payment:
        logger.warning("Payment %s not found", payment_id)
        return

    transaction = await transaction_repo.get_by_payment_id(payment_id)
    if not transaction:
        logger.warning("Transaction for payment %s not found", payment_id)
        await payment_repo.set_status(payment, PaymentStatus.FAILED)
        return

    attempt = 0
    while attempt < 3:
        attempt += 1
        try:
            await gateway.charge(payment.id, payment.user_id, float(payment.amount))
            break
        except Exception as exc:
            logger.warning("Gateway error for payment %s attempt %s: %s", payment.id, attempt, exc)
            if attempt >= 3:
                async with session.begin():
                    await payment_repo.set_status(payment, PaymentStatus.FAILED)
                    await transaction_repo.set_status(transaction, TransactionStatus.FAILED)
                return
            await asyncio.sleep(2 ** attempt)

    async with session.begin():
        user = await user_repo.get_by_id(payment.user_id)
        if not user:
            await payment_repo.set_status(payment, PaymentStatus.FAILED)
            await transaction_repo.set_status(transaction, TransactionStatus.FAILED)
            return

        if transaction.type == TransactionType.DEPOSIT:
            net_amount = float(payment.amount - payment.commission)
            user.deposit(net_amount)
        else:
            total_amount = float(payment.amount + payment.commission)
            try:
                user.withdraw(total_amount)
            except UserInsufficientFundsError:
                await payment_repo.set_status(payment, PaymentStatus.FAILED)
                await transaction_repo.set_status(transaction, TransactionStatus.FAILED)
                return

        await user_repo.save(user)
        await payment_repo.set_status(payment, PaymentStatus.SUCCESS)
        await transaction_repo.set_status(transaction, TransactionStatus.SUCCESS)


async def worker_loop(poll_interval: float = 1.0, batch_size: int = 10) -> None:
    gateway = HttpPaymentGatewayClient()
    try:
        while True:
            async with AsyncSessionLocal() as session:
                payment_repo = PaymentRepository(session)
                async with session.begin():
                    payments = await payment_repo.claim_pending(limit=batch_size)
                for payment in payments:
                    await process_payment(session, payment.id, gateway)
            await asyncio.sleep(poll_interval)
    finally:
        await gateway.close()


def run() -> None:
    logging.basicConfig(level=settings.log_level)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    run()
