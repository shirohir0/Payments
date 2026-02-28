from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.v1.schemas.payment import DepositRequestSchema, WithdrawRequestSchema
from app.api.v1.schemas.users import CreateUserSchema
from app.application.dto.payment import DepositDTO
from app.domain.entities.user import User
from app.domain.exceptions import InvalidIdempotencyKeyError, InvalidMoneyError
from app.domain.money import commission_for, money


@pytest.mark.parametrize(
    "value", ["NaN", "Infinity", "-Infinity", "0.001", "-0.01", "10000000000.00", True]
)
def test_money_rejects_nonfinite_precision_negative_and_overflow(value):
    with pytest.raises(InvalidMoneyError):
        money(value)


@pytest.mark.parametrize("value", ["0", "0.00", "-0.00"])
def test_payment_amount_must_be_positive(value):
    with pytest.raises(InvalidMoneyError):
        money(value, positive=True)


def test_fee_uses_decimal_half_up():
    assert commission_for(Decimal("0.25"), Decimal("0.02")) == Decimal("0.01")
    assert commission_for(Decimal("1.00"), Decimal("0.02")) == Decimal("0.02")
    assert money("1.0200") == Decimal("1.02")


def test_domain_balance_arithmetic_is_exact():
    user = User(id=1, balance="0.10")
    user.deposit("0.20")
    assert user.balance == Decimal("0.30")
    user.withdraw("0.30")
    assert user.balance == Decimal("0.00")


@pytest.mark.parametrize("key", [None, "", " ", "has space", "\n", "Г©", "x" * 65])
def test_dto_rejects_invalid_idempotency_keys(key):
    with pytest.raises(InvalidIdempotencyKeyError):
        DepositDTO(user_id=1, amount="1.00", idempotency_key=key)


def test_api_money_accepts_decimal_strings_without_precision_loss():
    request = DepositRequestSchema(user_id=1, deposit="1234567890.12")
    assert request.deposit == Decimal("1234567890.12")
    assert request.model_dump(mode="json")["deposit"] == "1234567890.12"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0.001", "-1", "0", "10000000000.00"])
def test_api_payment_schema_rejects_invalid_amounts(value):
    with pytest.raises(ValidationError):
        WithdrawRequestSchema(user_id=1, amount=value)


def test_zero_starting_balance_is_allowed_but_extra_fields_are_not():
    assert CreateUserSchema(balance="0.00").balance == Decimal("0.00")
    with pytest.raises(ValidationError):
        CreateUserSchema(balance="0", reserved_balance="50")
