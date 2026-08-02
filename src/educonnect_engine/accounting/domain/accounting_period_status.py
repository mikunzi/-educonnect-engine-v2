"""Accounting period lifecycle statuses."""

from enum import StrEnum


class AccountingPeriodStatus(StrEnum):
    """Allowed lifecycle states for accounting periods."""

    OPEN = "open"
    CLOSED = "closed"
    LOCKED = "locked"
