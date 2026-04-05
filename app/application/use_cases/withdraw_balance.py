from app.application.use_cases.payment_command import PaymentCommand


class WithdrawBalanceUseCase(PaymentCommand):
    operation = "withdraw"
