"""RecordJournalEntry use case."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.repositories import JournalEntryRepository
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


@dataclass(frozen=True, slots=True)
class RecordJournalEntryCommand:
    """Input payload for recording a journal entry."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    journal_code: JournalCode
    reference: JournalReference
    posting_date: date
    lines: tuple[JournalLine, ...]


@dataclass(frozen=True, slots=True)
class RecordJournalEntry:
    """Application service orchestrating journal entry recording."""

    repository: JournalEntryRepository
    id_generator: Callable[[], JournalEntryId]

    def execute(self, command: RecordJournalEntryCommand) -> JournalEntry:
        entry = JournalEntry.from_recorded(
            id=self.id_generator(),
            legal_entity_id=command.legal_entity_id,
            fiscal_year=command.fiscal_year,
            journal_code=command.journal_code,
            reference=command.reference,
            posting_date=command.posting_date,
            lines=command.lines,
        )
        self.repository.add(entry)
        return entry
