"""Unit tests for RecordJournalEntry use case."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from educonnect_engine.accounting.application.record_journal_entry import (
    RecordJournalEntry,
    RecordJournalEntryCommand,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.repositories import JournalEntryRepository
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _InMemoryJournalEntryRepository(JournalEntryRepository):
    added_entries: list[JournalEntry]

    def add(self, entry: JournalEntry) -> None:
        self.added_entries.append(entry)


def _line(side: DebitCreditSide, amount: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value="1000"),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
    )


def test_record_journal_entry_creates_and_persists_entry() -> None:
    repository = _InMemoryJournalEntryRepository(added_entries=[])

    def generate_id() -> JournalEntryId:
        return JournalEntryId(value="JE-001")

    use_case = RecordJournalEntry(repository=repository, id_generator=generate_id)

    command = RecordJournalEntryCommand(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line(DebitCreditSide.DEBIT, "10.00"),
            _line(DebitCreditSide.CREDIT, "10.00"),
        ),
    )

    result = use_case.execute(command)

    assert result.id == JournalEntryId(value="JE-001")
    assert result.status is JournalEntryStatus.RECORDED
    assert result.posted_at is None
    assert repository.added_entries == [result]
