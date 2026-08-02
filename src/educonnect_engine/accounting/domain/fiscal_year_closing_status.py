"""Fiscal year closing lifecycle statuses."""

from enum import StrEnum


class FiscalYearClosingStatus(StrEnum):
    """Allowed lifecycle states for fiscal year closing aggregate."""

    OPEN = "open"
    CLOSED = "closed"
