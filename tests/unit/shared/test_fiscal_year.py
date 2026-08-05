"""Unit tests for FiscalYear value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear


def test_fiscal_year_creation_success() -> None:
    year = FiscalYear(value=2026)

    assert year.value == 2026


@pytest.mark.parametrize("value", [1900, 9999])
def test_fiscal_year_accepts_boundaries(value: int) -> None:
    assert FiscalYear(value=value).value == value


def test_fiscal_year_value_equality() -> None:
    assert FiscalYear(value=2026) == FiscalYear(value=2026)


def test_fiscal_year_is_frozen_and_has_slots() -> None:
    year = FiscalYear(value=2026)

    with pytest.raises(FrozenInstanceError):
        type(year).__setattr__(year, "value", 2027)

    assert not hasattr(year, "__dict__")


@pytest.mark.parametrize("value", [1899, 10000])
def test_fiscal_year_rejects_out_of_range(value: int) -> None:
    with pytest.raises(ValueError):
        FiscalYear(value=value)
