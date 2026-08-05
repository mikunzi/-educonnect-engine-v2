"""Unit tests for AccountNumber value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber


@pytest.mark.parametrize("value", ["1000", "1020", "3000"])
def test_account_number_accepts_valid_four_digits(value: str) -> None:
    number = AccountNumber(value=value)

    assert number.value == value


@pytest.mark.parametrize(
    "value",
    ["", " 1000", "1000 ", "10 00", "ABCD", "10A0", "+100", "-100", "100", "10000"],
)
def test_account_number_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        AccountNumber(value=value)


def test_account_number_value_equality() -> None:
    assert AccountNumber(value="1000") == AccountNumber(value="1000")


def test_account_number_is_frozen_and_has_slots() -> None:
    number = AccountNumber(value="1000")

    with pytest.raises(FrozenInstanceError):
        type(number).__setattr__(number, "value", "1020")

    assert not hasattr(number, "__dict__")
