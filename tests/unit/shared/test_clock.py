"""Unit tests for shared clock primitive."""

from datetime import UTC

from educonnect_engine.shared.clock import Clock


def test_clock_now_is_timezone_aware() -> None:
    clock = Clock()
    now = clock.now_utc()

    assert now.tzinfo is not None
    assert now.tzinfo is UTC


def test_clock_today_matches_now_date() -> None:
    clock = Clock(tz=UTC)

    assert clock.today() == clock.now_utc().date()
