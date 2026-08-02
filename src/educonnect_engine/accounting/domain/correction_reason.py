"""Correction reason value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CorrectionReason:
    """Immutable reason attached to a reversal entry."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("correction reason must not be empty")
        if self.value != self.value.strip():
            raise ValueError("correction reason must not have surrounding spaces")
        if len(self.value) > 256:
            raise ValueError("correction reason must not exceed 256 characters")
        if any(ord(char) < 32 or ord(char) == 127 for char in self.value):
            raise ValueError("correction reason must not contain control characters")
