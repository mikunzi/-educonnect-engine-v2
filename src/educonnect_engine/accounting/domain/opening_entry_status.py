"""Opening entry lifecycle status."""

from enum import StrEnum


class OpeningEntryStatus(StrEnum):
    """Business states of an opening entry."""

    GENERATED = "generated"
    POSTED = "posted"

    @property
    def is_final(self) -> bool:
        """Return whether no further lifecycle transition is permitted."""
        return self is OpeningEntryStatus.POSTED