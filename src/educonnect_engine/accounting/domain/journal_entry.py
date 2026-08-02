"""Journal entry aggregate."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money

from .correction_reason import CorrectionReason
from .debit_credit_side import DebitCreditSide
from .journal_entry_id import JournalEntryId
from .journal_entry_status import JournalEntryStatus
from .journal_line import JournalLine


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """Immutable journal entry aggregate with accounting invariants."""

    id: JournalEntryId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    journal_code: JournalCode
    reference: JournalReference
    posting_date: date
    version: int
    status: JournalEntryStatus
    posted_at: datetime | None
    lines: tuple[JournalLine, ...]
    correction_of_entry_id: JournalEntryId | None = None
    correction_reason: CorrectionReason | None = None

    @classmethod
    def from_recorded(
        cls,
        *,
        id: JournalEntryId,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        journal_code: JournalCode,
        reference: JournalReference,
        posting_date: date,
        lines: tuple[JournalLine, ...],
    ) -> JournalEntry:
        return cls(
            id=id,
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year,
            journal_code=journal_code,
            reference=reference,
            posting_date=posting_date,
            version=0,
            status=JournalEntryStatus.RECORDED,
            posted_at=None,
            lines=lines,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.status, JournalEntryStatus):
            raise ValueError("journal entry status must be a JournalEntryStatus")
        if self.version < 0:
            raise ValueError("journal entry version must be greater than or equal to 0")

        if self.status is JournalEntryStatus.RECORDED and self.posted_at is not None:
            raise ValueError("posted_at must be None for recorded journal entries")
        if self.status is JournalEntryStatus.POSTED and self.posted_at is None:
            raise ValueError("posted entries must define posted_at")
        if (self.correction_of_entry_id is None) != (self.correction_reason is None):
            raise ValueError("correction_of_entry_id and correction_reason must be set together")
        if len(self.lines) < 2:
            raise ValueError("journal entry must contain at least 2 lines")
        if any(not isinstance(line, JournalLine) for line in self.lines):
            raise TypeError("lines must contain only JournalLine instances")

        expected_currency = self.lines[0].amount.currency
        if any(line.amount.currency != expected_currency for line in self.lines):
            raise ValueError("journal entry lines must use a single currency")

        if self.total_debit().amount != self.total_credit().amount:
            raise ValueError("journal entry must be balanced")

    def replace_lines(self, lines: tuple[JournalLine, ...]) -> JournalEntry:
        return JournalEntry.from_recorded(
            id=self.id,
            legal_entity_id=self.legal_entity_id,
            fiscal_year=self.fiscal_year,
            journal_code=self.journal_code,
            reference=self.reference,
            posting_date=self.posting_date,
            lines=lines,
        )

    def post(self, posted_at: datetime) -> JournalEntry:
        if self.status is not JournalEntryStatus.RECORDED:
            raise ValueError("journal entry must be RECORDED before posting")
        if self.posted_at is not None:
            raise ValueError("recorded journal entry must have posted_at set to None")
        if posted_at.tzinfo is None:
            raise ValueError("posted_at must be timezone-aware")
        if posted_at.tzinfo is not UTC:
            raise ValueError("posted_at timezone must be UTC")

        return replace(
            self,
            version=self.version + 1,
            status=JournalEntryStatus.POSTED,
            posted_at=posted_at,
        )

    def build_reversal(
        self,
        *,
        reversal_entry_id: JournalEntryId,
        reversal_fiscal_year: FiscalYear,
        reversal_journal_code: JournalCode,
        reversal_reference: JournalReference,
        reversal_date: date,
        correction_reason: CorrectionReason,
    ) -> JournalEntry:
        if self.status is not JournalEntryStatus.POSTED:
            raise ValueError("original journal entry must be POSTED")
        if reversal_date < self.posting_date:
            raise ValueError("reversal_date must not be earlier than original posting_date")
        if reversal_date.year != reversal_fiscal_year.value:
            raise ValueError("reversal_date is incompatible with reversal fiscal year")
        if not isinstance(correction_reason, CorrectionReason):
            raise ValueError("correction_reason must be a CorrectionReason")

        reversed_lines = tuple(
            JournalLine(
                account_number=line.account_number,
                side=(
                    DebitCreditSide.CREDIT
                    if line.side is DebitCreditSide.DEBIT
                    else DebitCreditSide.DEBIT
                ),
                amount=line.amount,
                description=line.description,
            )
            for line in self.lines
        )

        return JournalEntry(
            id=reversal_entry_id,
            legal_entity_id=self.legal_entity_id,
            fiscal_year=reversal_fiscal_year,
            journal_code=reversal_journal_code,
            reference=reversal_reference,
            posting_date=reversal_date,
            version=0,
            status=JournalEntryStatus.RECORDED,
            posted_at=None,
            lines=reversed_lines,
            correction_of_entry_id=self.id,
            correction_reason=correction_reason,
        )

    def currency(self) -> Currency:
        return self.lines[0].amount.currency

    def total_debit(self) -> Money:
        total = sum(
            (line.amount.amount for line in self.lines if line.side is DebitCreditSide.DEBIT),
            start=Decimal("0"),
        )
        return Money(amount=total, currency=self.currency())

    def total_credit(self) -> Money:
        total = sum(
            (line.amount.amount for line in self.lines if line.side is DebitCreditSide.CREDIT),
            start=Decimal("0"),
        )
        return Money(amount=total, currency=self.currency())
