from enum import Enum


class PaymentDirection(str, Enum):
    debit = "debit"
    credit = "credit"
