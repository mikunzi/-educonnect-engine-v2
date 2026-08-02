"""Debit/credit side enumeration."""

from enum import StrEnum


class DebitCreditSide(StrEnum):
    """Accounting line side in double-entry bookkeeping."""

    DEBIT = "debit"
    CREDIT = "credit"
