"""Unit tests for IdempotencyKey value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey


@pytest.mark.parametrize("value", ["POST-001", "post.entry_1", "key:2026-01"])
def test_idempotency_key_accepts_valid_values(value: str) -> None:
    key = IdempotencyKey(value=value)

    assert key.value == value


@pytest.mark.parametrize(
    "value",
    ["", " key", "key ", "a" * 129, "bad/key", "bad key"],
)
def test_idempotency_key_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        IdempotencyKey(value=value)


def test_idempotency_key_accepts_max_length() -> None:
    value = "a" * 128

    assert IdempotencyKey(value=value).value == value


def test_idempotency_key_value_equality() -> None:
    assert IdempotencyKey(value="POST-001") == IdempotencyKey(value="POST-001")


def test_idempotency_key_is_frozen_and_has_slots() -> None:
    key = IdempotencyKey(value="POST-001")

    with pytest.raises(FrozenInstanceError):
        type(key).__setattr__(key, "value", "POST-002")

    assert not hasattr(key, "__dict__")
