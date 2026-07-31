"""Unit tests for shared money value object."""

from decimal import Decimal

import pytest

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


def test_money_creation_success() -> None:
    value = Money(amount=Decimal("12.50"), currency=Currency(code="CHF"))

    assert value.amount == Decimal("12.50")
    assert value.currency.code == "CHF"


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity")])
def test_money_rejects_non_finite_amount(amount: Decimal) -> None:
    with pytest.raises(ValueError, match="money amount must be finite"):
        Money(amount=amount, currency=Currency(code="CHF"))
