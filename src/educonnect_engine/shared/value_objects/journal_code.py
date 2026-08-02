"""Journal code value object."""

import re
from dataclasses import dataclass

_JOURNAL_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class JournalCode:
    """Immutable normalized journal code."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("journal code must not be empty")
        if self.value != self.value.strip():
            raise ValueError("journal code must not have surrounding spaces")
        if len(self.value) < 2 or len(self.value) > 16:
            raise ValueError("journal code length must be between 2 and 16")
        if _JOURNAL_CODE_PATTERN.fullmatch(self.value) is None:
            raise ValueError("journal code must contain only A-Z, 0-9, '_' or '-' characters")
