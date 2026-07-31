"""Unit tests for shared percentage value object."""

from decimal import Decimal

import pytest

from educonnect_engine.shared.value_objects.percentage import Percentage


def test_percentage_creation_success() -> None:
    value = Percentage(value=Decimal("15.5"))

    assert value.value == Decimal("15.5")


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("100.01")])
def test_percentage_rejects_out_of_range(value: Decimal) -> None:
    with pytest.raises(ValueError, match="percentage must be between 0 and 100"):
        Percentage(value=value)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_percentage_rejects_non_finite(value: Decimal) -> None:
    with pytest.raises(ValueError, match="percentage must be finite"):
        Percentage(value=value)
