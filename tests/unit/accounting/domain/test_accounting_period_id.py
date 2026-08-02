"""Unit tests for AccountingPeriodId value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId


@pytest.mark.parametrize("value", ["PER-2026-01", "period_01", "batch.2026"])
def test_accounting_period_id_accepts_valid_values(value: str) -> None:
    period_id = AccountingPeriodId(value=value)

    assert period_id.value == value


@pytest.mark.parametrize("value", ["", " PER-1", "PER-1 ", "bad/id", "a" * 65])
def test_accounting_period_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        AccountingPeriodId(value=value)


def test_accounting_period_id_is_frozen_and_has_slots() -> None:
    period_id = AccountingPeriodId(value="PER-2026-01")

    with pytest.raises(FrozenInstanceError):
        period_id.value = "PER-2026-02"

    assert not hasattr(period_id, "__dict__")
