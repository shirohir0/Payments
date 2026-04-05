from app.application.use_cases.payment_command import PaymentCommand


class DepositBalanceUseCase(PaymentCommand):
    operation = "deposit"
