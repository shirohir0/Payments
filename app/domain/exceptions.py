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
