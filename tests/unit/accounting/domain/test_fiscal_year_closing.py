"""Unit tests for FiscalYearClosing aggregate."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from educonnect_engine.accounting.domain.closing_timestamp import ClosingTimestamp
from educonnect_engine.accounting.domain.fiscal_year_closing import (
    FiscalYearClosing,
    FiscalYearClosingTransitionError,
    FiscalYearClosingVersionConflictError,
)
from educonnect_engine.accounting.domain.fiscal_year_closing_id import FiscalYearClosingId
from educonnect_engine.accounting.domain.fiscal_year_closing_status import FiscalYearClosingStatus
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


def _open_closing() -> FiscalYearClosing:
    return FiscalYearClosing.open(
        id=FiscalYearClosingId(value="FYC-2026"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
    )


def test_fiscal_year_closing_open_factory_creates_open_version_zero() -> None:
    closing = _open_closing()

    assert closing.status is FiscalYearClosingStatus.OPEN
    assert closing.version == 0
    assert closing.closing_timestamp is None


def test_fiscal_year_closing_close_transitions_to_closed_and_increments_version() -> None:
    closing = _open_closing().close(
        timestamp=ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
        expected_version=0,
    )

    assert closing.status is FiscalYearClosingStatus.CLOSED
    assert closing.version == 1
    assert closing.closing_timestamp == ClosingTimestamp(
        value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
    )


def test_fiscal_year_closing_close_rejects_version_mismatch() -> None:
    with pytest.raises(FiscalYearClosingVersionConflictError):
        _open_closing().close(
            timestamp=ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
            expected_version=1,
        )


def test_fiscal_year_closing_close_rejects_already_closed_transition() -> None:
    closed = _open_closing().close(
        timestamp=ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
        expected_version=0,
    )

    with pytest.raises(FiscalYearClosingTransitionError):
        closed.close(
            timestamp=ClosingTimestamp(value=datetime(2027, 1, 1, 0, 0, tzinfo=UTC)),
            expected_version=1,
        )


def test_fiscal_year_closing_rejects_invalid_open_state() -> None:
    with pytest.raises(ValueError, match="OPEN"):
        FiscalYearClosing(
            id=FiscalYearClosingId(value="FYC-2026"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            status=FiscalYearClosingStatus.OPEN,
            closing_timestamp=ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
            version=0,
        )


def test_fiscal_year_closing_rejects_invalid_closed_state() -> None:
    with pytest.raises(ValueError, match="CLOSED"):
        FiscalYearClosing(
            id=FiscalYearClosingId(value="FYC-2026"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            status=FiscalYearClosingStatus.CLOSED,
            closing_timestamp=None,
            version=1,
        )


def test_fiscal_year_closing_rejects_negative_version() -> None:
    with pytest.raises(ValueError, match="version"):
        FiscalYearClosing(
            id=FiscalYearClosingId(value="FYC-2026"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            status=FiscalYearClosingStatus.OPEN,
            closing_timestamp=None,
            version=-1,
        )


def test_fiscal_year_closing_rejects_invalid_status_type() -> None:
    with pytest.raises(ValueError, match="status"):
        FiscalYearClosing(
            id=FiscalYearClosingId(value="FYC-2026"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            status="closed",  # type: ignore[arg-type]
            closing_timestamp=ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
            version=1,
        )


def test_fiscal_year_closing_is_frozen_and_has_slots() -> None:
    closing = _open_closing()

    with pytest.raises(FrozenInstanceError):
        closing.version = 1

    assert not hasattr(closing, "__dict__")
