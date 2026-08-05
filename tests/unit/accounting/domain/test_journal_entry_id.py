"""Unit tests for JournalEntryId value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId


@pytest.mark.parametrize("value", ["JE-001", "entry_2026", "batch.01"])
def test_journal_entry_id_accepts_valid_values(value: str) -> None:
    identifier = JournalEntryId(value=value)

    assert identifier.value == value


@pytest.mark.parametrize("value", ["", " JE-001", "JE-001 ", "id!", "a" * 65])
def test_journal_entry_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        JournalEntryId(value=value)


def test_journal_entry_id_value_equality() -> None:
    assert JournalEntryId(value="JE-001") == JournalEntryId(value="JE-001")


def test_journal_entry_id_is_frozen_and_has_slots() -> None:
    identifier = JournalEntryId(value="JE-001")

    with pytest.raises(FrozenInstanceError):
        type(identifier).__setattr__(identifier, "value", "JE-002")

    assert not hasattr(identifier, "__dict__")
