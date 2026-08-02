"""Unit tests for ClosingTimestamp value object."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from educonnect_engine.accounting.domain.closing_timestamp import ClosingTimestamp


def test_closing_timestamp_accepts_utc_timezone_aware_datetime() -> None:
    timestamp = ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC))

    assert timestamp.value == datetime(2026, 12, 31, 23, 59, tzinfo=UTC)


def test_closing_timestamp_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59))


def test_closing_timestamp_rejects_non_utc_datetime() -> None:
    with pytest.raises(ValueError, match="UTC"):
        ClosingTimestamp(
            value=datetime(2026, 12, 31, 23, 59, tzinfo=timezone(timedelta(hours=1))),
        )


def test_closing_timestamp_is_frozen_and_has_slots() -> None:
    timestamp = ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC))

    with pytest.raises(FrozenInstanceError):
        timestamp.value = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)

    assert not hasattr(timestamp, "__dict__")
