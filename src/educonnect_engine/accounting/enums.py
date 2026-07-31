"""Accounting enumerations used by domain scaffolds."""

from enum import StrEnum


class AccountCategory(StrEnum):
    """High-level account categories.

    Values are scaffolds and do not encode business computation rules.
    """

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class NormalBalance(StrEnum):
    """Normal balance orientation for an account."""

    DEBIT = "debit"
    CREDIT = "credit"


class FinancialStatement(StrEnum):
    """Primary financial statement assignment for an account."""

    BALANCE_SHEET = "balance_sheet"
    INCOME_STATEMENT = "income_statement"
