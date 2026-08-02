"""Unit tests for FiscalYearClosingId value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.fiscal_year_closing_id import FiscalYearClosingId


@pytest.mark.parametrize("value", ["FYC-2026", "closing_01", "closing.batch-1"])
def test_fiscal_year_closing_id_accepts_valid_values(value: str) -> None:
    closing_id = FiscalYearClosingId(value=value)

    assert closing_id.value == value


@pytest.mark.parametrize("value", ["", " FYC-2026", "FYC-2026 ", "bad/id", "a" * 65])
def test_fiscal_year_closing_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        FiscalYearClosingId(value=value)


def test_fiscal_year_closing_id_is_frozen_and_has_slots() -> None:
    closing_id = FiscalYearClosingId(value="FYC-2026")

    with pytest.raises(FrozenInstanceError):
        closing_id.value = "FYC-2027"

    assert not hasattr(closing_id, "__dict__")
