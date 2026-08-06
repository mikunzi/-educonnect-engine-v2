"""Unit tests for OpeningEntryStatus enum."""

from educonnect_engine.accounting.domain.opening_entry_status import OpeningEntryStatus


def test_opening_entry_status_values_are_stable() -> None:
    assert OpeningEntryStatus.GENERATED.value == "generated"
    assert OpeningEntryStatus.POSTED.value == "posted"


def test_opening_entry_posted_status_is_final() -> None:
    assert OpeningEntryStatus.POSTED.is_final is True
    assert OpeningEntryStatus.GENERATED.is_final is False
