"""Account category enum for chart-of-accounts metadata."""

from enum import StrEnum


class AccountCategory(StrEnum):
    """Stable high-level category of an account."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"