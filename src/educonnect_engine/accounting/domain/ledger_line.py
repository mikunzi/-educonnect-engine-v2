"""Ledger line projection value object."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.money import Money

from .account_number import AccountNumber
from .debit_credit_side import DebitCreditSide
from .journal_entry_id import JournalEntryId


@dataclass(frozen=True, slots=True)
class LedgerLine:
    """Projected immutable ledger line traceable to one journal line."""

    journal_entry_id: JournalEntryId
    posting_date: date
    posted_at: datetime
    journal_code: JournalCode
    reference: JournalReference
    account_number: AccountNumber
    side: DebitCreditSide
    amount: Money
    description: str
    line_index: int

    def __post_init__(self) -> None:
        if self.posted_at.tzinfo is None:
            raise ValueError("posted_at must be timezone-aware")
        if self.posted_at.tzinfo is not UTC:
            raise ValueError("posted_at timezone must be UTC")
        if not isinstance(self.line_index, int):
            raise TypeError("line_index must be an int")
        if self.line_index < 0:
            raise ValueError("line_index must be greater than or equal to 0")
        if self.amount.amount <= 0:
            raise ValueError("ledger line amount must be strictly positive")

    def sort_key(self) -> tuple[date, datetime, str, int]:
        """Return deterministic ledger ordering key."""
        return (
            self.posting_date,
            self.posted_at,
            self.journal_entry_id.value,
            self.line_index,
        )
