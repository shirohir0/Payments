"""Exact monetary values for the service's single, two-decimal currency."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.domain.exceptions import InvalidIdempotencyKeyError, InvalidMoneyError

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_MONEY = Decimal("9999999999.99")


def money(value: Decimal | str | int | float, *, positive: bool = False) -> Decimal:
    """Validate at the boundary; never silently round a caller's amount."""
    try:
        if isinstance(value, bool):
            raise InvalidMoneyError("A monetary amount must be a decimal number")
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if not amount.is_finite() or amount < ZERO or amount > MAX_MONEY:
            raise InvalidMoneyError("Amount must be finite and between 0 and 9999999999.99")
        quantized = amount.quantize(CENT, rounding=ROUND_HALF_UP)
        if amount != quantized:
            raise InvalidMoneyError("Amounts may have at most two decimal places")
        if positive and quantized <= ZERO:
            raise InvalidMoneyError("Amount must be greater than zero")
        return quantized
    except (InvalidOperation, TypeError, ValueError) as exc:
        if isinstance(exc, InvalidMoneyError):
            raise
        raise InvalidMoneyError("A monetary amount must be a decimal number") from exc


def commission_for(amount: Decimal, rate: Decimal | str | float) -> Decimal:
    """Round only the calculated fee, explicitly using commercial rounding."""
    try:
        decimal_rate = rate if isinstance(rate, Decimal) else Decimal(str(rate))
        if not decimal_rate.is_finite() or not ZERO <= decimal_rate < Decimal("1"):
            raise InvalidMoneyError("Commission rate must be between zero and one")
        fee = (amount * decimal_rate).quantize(CENT, rounding=ROUND_HALF_UP)
        return money(fee)
    except InvalidOperation as exc:
        raise InvalidMoneyError("Invalid commission calculation") from exc


def idempotency_key(value: str | None) -> str:
    """Keys are opaque: validate without changing whitespace or case."""
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 64
        or not value.strip()
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
    ):
        raise InvalidIdempotencyKeyError(
            "Idempotency-Key must contain 1 to 64 visible ASCII characters"
        )
    return value
