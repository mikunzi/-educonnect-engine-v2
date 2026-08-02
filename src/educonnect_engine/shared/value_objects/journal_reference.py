"""Journal reference value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JournalReference:
    """Immutable reference identifier for journal entries."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("journal reference must not be empty")
        if self.value != self.value.strip():
            raise ValueError("journal reference must not have surrounding spaces")
        if len(self.value) > 64:
            raise ValueError("journal reference must not exceed 64 characters")
        if any(ord(char) < 32 or ord(char) == 127 for char in self.value):
            raise ValueError("journal reference must not contain control characters")
