"""Unit tests for shared type aliases module."""

from datetime import date, datetime

from educonnect_engine.shared.types import DateProvider, DateTimeProvider, ErrorMessage


def _today() -> date:
    return date(2026, 1, 1)


def _now() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0)


def test_type_alias_usage_examples() -> None:
    date_provider: DateProvider = _today
    datetime_provider: DateTimeProvider = _now
    message: ErrorMessage = "ok"

    assert date_provider() == date(2026, 1, 1)
    assert datetime_provider() == datetime(2026, 1, 1, 0, 0, 0)
    assert message == "ok"
