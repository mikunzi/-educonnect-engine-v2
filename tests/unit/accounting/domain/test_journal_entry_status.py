"""Unit tests for JournalEntryStatus enum."""

from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus


def test_journal_entry_status_recorded_only() -> None:
    assert list(JournalEntryStatus) == [JournalEntryStatus.RECORDED, JournalEntryStatus.POSTED]
    assert JournalEntryStatus.RECORDED.value == "recorded"
    assert JournalEntryStatus.POSTED.value == "posted"
