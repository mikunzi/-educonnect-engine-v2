"""Unit tests for AccountingPeriod value object."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from educonnect_engine.shared.value_objects.accounting_period import AccountingPeriod


def test_accounting_period_creation_success() -> None:
    period = AccountingPeriod(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))

    assert period.start_date == date(2026, 1, 1)
    assert period.end_date == date(2026, 12, 31)


def test_accounting_period_accepts_same_start_and_end_date() -> None:
    same_day = date(2026, 1, 1)

    period = AccountingPeriod(start_date=same_day, end_date=same_day)

    assert period.start_date == same_day
    assert period.end_date == same_day


def test_accounting_period_value_equality() -> None:
    assert AccountingPeriod(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    ) == AccountingPeriod(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )


def test_accounting_period_is_frozen_and_has_slots() -> None:
    period = AccountingPeriod(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))

    with pytest.raises(FrozenInstanceError):
        type(period).__setattr__(period, "end_date", date(2027, 1, 1))

    assert not hasattr(period, "__dict__")


def test_accounting_period_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="start_date"):
        AccountingPeriod(start_date=date(2026, 12, 31), end_date=date(2026, 1, 1))


def test_accounting_period_contains_is_inclusive() -> None:
    period = AccountingPeriod(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))

    assert period.contains(date(2026, 1, 1)) is True
    assert period.contains(date(2026, 1, 15)) is True
    assert period.contains(date(2026, 1, 31)) is True
    assert period.contains(date(2025, 12, 31)) is False
    assert period.contains(date(2026, 2, 1)) is False
