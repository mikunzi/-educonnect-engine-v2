"""Account classification for financial statement projections."""

from enum import StrEnum


class AccountClassification(StrEnum):
    """Classification of accounts for statement projections."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"
