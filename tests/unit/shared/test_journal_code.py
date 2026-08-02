"""Unit tests for JournalCode value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.shared.value_objects.journal_code import JournalCode


def test_journal_code_creation_success() -> None:
    code = JournalCode(value="GEN_01")

    assert code.value == "GEN_01"


@pytest.mark.parametrize("value", ["AB", "X" * 16])
def test_journal_code_accepts_length_boundaries(value: str) -> None:
    assert JournalCode(value=value).value == value


def test_journal_code_value_equality() -> None:
    assert JournalCode(value="GEN_01") == JournalCode(value="GEN_01")


def test_journal_code_is_frozen_and_has_slots() -> None:
    code = JournalCode(value="GEN_01")

    with pytest.raises(FrozenInstanceError):
        code.value = "SALES"

    assert not hasattr(code, "__dict__")


@pytest.mark.parametrize(
    "value",
    ["", " G1", "G1 ", "g1", "A", "X" * 17, "AB!", "AB.C"],
)
def test_journal_code_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        JournalCode(value=value)
