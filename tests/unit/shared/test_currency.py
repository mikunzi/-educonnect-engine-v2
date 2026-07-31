"""Unit tests for shared currency value object."""

import pytest

from educonnect_engine.shared.value_objects.currency import Currency


def test_currency_creation_success() -> None:
    currency = Currency(code="CHF")

    assert currency.code == "CHF"


@pytest.mark.parametrize("code", ["", "CH", "CHFF", "12F", "chf"])
def test_currency_rejects_invalid_code(code: str) -> None:
    with pytest.raises(ValueError):
        Currency(code=code)
