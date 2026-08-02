"""Unit tests for CorrectionReason value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.correction_reason import CorrectionReason


def test_correction_reason_accepts_valid_value() -> None:
    reason = CorrectionReason(value="Duplicate posting detected")

    assert reason.value == "Duplicate posting detected"


@pytest.mark.parametrize(
    "value",
    ["", " reason", "reason ", "x" * 257, "fix\nnow", "fix\tsoon", "bad\x7f"],
)
def test_correction_reason_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        CorrectionReason(value=value)


def test_correction_reason_accepts_max_length() -> None:
    value = "x" * 256

    assert CorrectionReason(value=value).value == value


def test_correction_reason_is_frozen_and_has_slots() -> None:
    reason = CorrectionReason(value="Manual correction")

    with pytest.raises(FrozenInstanceError):
        reason.value = "Other"

    assert not hasattr(reason, "__dict__")
