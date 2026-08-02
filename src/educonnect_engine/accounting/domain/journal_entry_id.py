"""Journal entry identifier value object."""

import re
from dataclasses import dataclass

_JOURNAL_ENTRY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class JournalEntryId:
    """Immutable identifier for a journal entry aggregate."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("journal entry id must not be empty")
        if self.value != self.value.strip():
            raise ValueError("journal entry id must not have surrounding spaces")
        if len(self.value) > 64:
            raise ValueError("journal entry id must not exceed 64 characters")
        if _JOURNAL_ENTRY_ID_PATTERN.fullmatch(self.value) is None:
            raise ValueError("journal entry id contains invalid characters")
