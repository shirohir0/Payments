class UserError(Exception):
    pass


class UserNegativeBalanceError(UserError):
    pass


class UserNegativeAmountError(UserError):
    pass


class UserWithdrawAmountError(UserError):
    pass


class UserInsufficientFundsError(UserError):
    pass


class UserNotFoundError(UserError):
    pass


class InvalidMoneyError(ValueError):
    pass


class InvalidIdempotencyKeyError(ValueError):
    pass


class IdempotencyConflictError(UserError):
    pass
