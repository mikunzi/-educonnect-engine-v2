"""Unit tests for LegalEntityId value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


def test_legal_entity_id_creation_success() -> None:
    identifier = LegalEntityId(value="educonnect_sa-01")

    assert identifier.value == "educonnect_sa-01"


def test_legal_entity_id_value_equality() -> None:
    assert LegalEntityId(value="entity-01") == LegalEntityId(value="entity-01")


def test_legal_entity_id_is_frozen_and_has_slots() -> None:
    identifier = LegalEntityId(value="entity-01")

    with pytest.raises(FrozenInstanceError):
        identifier.value = "entity-02"

    assert not hasattr(identifier, "__dict__")


def test_legal_entity_id_accepts_64_characters() -> None:
    value = "a" * 64

    assert LegalEntityId(value=value).value == value


@pytest.mark.parametrize("value", ["", "  abc", "abc  ", "abc!", "a" * 65])
def test_legal_entity_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        LegalEntityId(value=value)
