"""Journal entry status enumeration."""

from enum import StrEnum


class JournalEntryStatus(StrEnum):
    """Journal entry lifecycle status for V1 step 2."""

    RECORDED = "recorded"
    POSTED = "posted"
