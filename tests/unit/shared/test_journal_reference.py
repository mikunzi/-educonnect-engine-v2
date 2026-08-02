"""Unit tests for JournalReference value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.shared.value_objects.journal_reference import JournalReference


def test_journal_reference_creation_success() -> None:
    reference = JournalReference(value="INV-2026-0001")

    assert reference.value == "INV-2026-0001"


def test_journal_reference_value_equality() -> None:
    assert JournalReference(value="INV-2026-0001") == JournalReference(value="INV-2026-0001")


def test_journal_reference_is_frozen_and_has_slots() -> None:
    reference = JournalReference(value="INV-2026-0001")

    with pytest.raises(FrozenInstanceError):
        reference.value = "INV-2026-0002"

    assert not hasattr(reference, "__dict__")


def test_journal_reference_accepts_64_characters() -> None:
    value = "R" * 64

    assert JournalReference(value=value).value == value


@pytest.mark.parametrize(
    "value",
    ["", " REF", "REF ", "R" * 65, "REF\n001", "REF\t001", "REF\x7f001"],
)
def test_journal_reference_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        JournalReference(value=value)
