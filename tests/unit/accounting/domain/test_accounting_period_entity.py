"""Unit tests for AccountingPeriod aggregate."""

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from educonnect_engine.accounting.domain.accounting_period import (
    AccountingPeriod,
    AccountingPeriodDateFiscalYearMismatchError,
    AccountingPeriodTransitionError,
    AccountingPeriodVersionConflictError,
)
from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId
from educonnect_engine.accounting.domain.accounting_period_status import AccountingPeriodStatus
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


def _period(
    *,
    period_id: str = "PER-2026-01",
    start_date: date = date(2026, 1, 1),
    end_date: date = date(2026, 1, 31),
    status: AccountingPeriodStatus = AccountingPeriodStatus.OPEN,
    version: int = 0,
) -> AccountingPeriod:
    return AccountingPeriod(
        id=AccountingPeriodId(value=period_id),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        start_date=start_date,
        end_date=end_date,
        status=status,
        version=version,
    )


def test_accounting_period_creation_success() -> None:
    period = _period()

    assert period.status is AccountingPeriodStatus.OPEN
    assert period.version == 0


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (date(2025, 12, 31), date(2026, 1, 15)),
        (date(2026, 1, 1), date(2027, 1, 1)),
    ],
)
def test_accounting_period_rejects_dates_outside_fiscal_year(
    start_date: date,
    end_date: date,
) -> None:
    with pytest.raises(AccountingPeriodDateFiscalYearMismatchError):
        _period(start_date=start_date, end_date=end_date)


def test_accounting_period_rejects_inverted_date_range() -> None:
    with pytest.raises(ValueError, match="start_date"):
        _period(start_date=date(2026, 2, 1), end_date=date(2026, 1, 31))


def test_accounting_period_rejects_invalid_status_type() -> None:
    with pytest.raises(ValueError, match="status"):
        AccountingPeriod(
            id=AccountingPeriodId(value="PER-2026-01"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            status="open",  # type: ignore[arg-type]
            version=0,
        )


def test_accounting_period_rejects_negative_version() -> None:
    with pytest.raises(ValueError, match="version"):
        _period(version=-1)


def test_accounting_period_close_transitions_open_to_closed() -> None:
    closed = _period(version=2).close(expected_version=2)

    assert closed.status is AccountingPeriodStatus.CLOSED
    assert closed.version == 3


def test_accounting_period_lock_transitions_closed_to_locked() -> None:
    locked = _period(status=AccountingPeriodStatus.CLOSED, version=4).lock(expected_version=4)

    assert locked.status is AccountingPeriodStatus.LOCKED
    assert locked.version == 5


def test_accounting_period_rejects_forbidden_transitions() -> None:
    with pytest.raises(AccountingPeriodTransitionError):
        _period(status=AccountingPeriodStatus.CLOSED).close(expected_version=0)

    with pytest.raises(AccountingPeriodTransitionError):
        _period(status=AccountingPeriodStatus.OPEN).lock(expected_version=0)

    with pytest.raises(AccountingPeriodTransitionError):
        _period(status=AccountingPeriodStatus.LOCKED).lock(expected_version=0)


def test_accounting_period_rejects_expected_version_mismatch() -> None:
    with pytest.raises(AccountingPeriodVersionConflictError):
        _period(version=3).close(expected_version=2)


def test_accounting_period_lock_rejects_expected_version_mismatch() -> None:
    with pytest.raises(AccountingPeriodVersionConflictError):
        _period(status=AccountingPeriodStatus.CLOSED, version=2).lock(expected_version=1)


def test_accounting_period_is_open_for_checks_status_and_date() -> None:
    open_period = _period(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    closed_period = _period(status=AccountingPeriodStatus.CLOSED)

    assert open_period.is_open_for(date(2026, 1, 1)) is True
    assert open_period.is_open_for(date(2026, 1, 31)) is True
    assert open_period.is_open_for(date(2026, 2, 1)) is False
    assert closed_period.is_open_for(date(2026, 1, 15)) is False


def test_accounting_period_overlaps_is_inclusive_for_same_scope() -> None:
    first = _period(period_id="PER-1", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    overlapping = _period(
        period_id="PER-2",
        start_date=date(2026, 1, 31),
        end_date=date(2026, 2, 15),
    )
    adjacent = _period(
        period_id="PER-3",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )

    assert first.overlaps(overlapping) is True
    assert first.overlaps(adjacent) is False


def test_accounting_period_overlaps_returns_false_for_different_scope() -> None:
    first = _period()
    second = AccountingPeriod(
        id=AccountingPeriodId(value="PER-2026-02"),
        legal_entity_id=LegalEntityId(value="entity-02"),
        fiscal_year=FiscalYear(value=2026),
        start_date=date(2026, 1, 15),
        end_date=date(2026, 2, 15),
        status=AccountingPeriodStatus.OPEN,
        version=0,
    )

    assert first.overlaps(second) is False


def test_accounting_period_overlaps_returns_false_for_different_fiscal_year() -> None:
    first = _period()
    second = AccountingPeriod(
        id=AccountingPeriodId(value="PER-2027-01"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2027),
        start_date=date(2027, 1, 1),
        end_date=date(2027, 1, 31),
        status=AccountingPeriodStatus.OPEN,
        version=0,
    )

    assert first.overlaps(second) is False


def test_accounting_period_is_frozen_and_has_slots() -> None:
    period = _period()

    with pytest.raises(FrozenInstanceError):
        type(period).__setattr__(period, "version", 1)

    assert not hasattr(period, "__dict__")
