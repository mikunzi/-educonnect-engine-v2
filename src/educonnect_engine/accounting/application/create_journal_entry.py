"""CreateJournalEntry use case."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.repositories import JournalEntryRepository, UnitOfWork
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class CreateJournalEntryUnitOfWork(UnitOfWork, Protocol):
    """UnitOfWork contract required by CreateJournalEntry handler."""

    @property
    def journal_entry_repository(self) -> JournalEntryRepository:
        """Journal entry repository bound to current transaction."""


@dataclass(frozen=True, slots=True)
class CreateJournalEntryCommand:
    """Input payload for creating one recorded journal entry."""

    journal_entry_id: JournalEntryId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    journal_code: JournalCode
    reference: JournalReference
    posting_date: date
    lines: tuple[JournalLine, ...]


@dataclass(frozen=True, slots=True)
class CreateJournalEntryResult:
    """Typed output returned by CreateJournalEntry."""

    journal_entry_id: JournalEntryId
    status: JournalEntryStatus
    version: int


@dataclass(frozen=True, slots=True)
class CreateJournalEntryHandler:
    """Transactional application service creating recorded journal entries."""

    uow: CreateJournalEntryUnitOfWork

    def execute(self, command: CreateJournalEntryCommand) -> CreateJournalEntryResult:
        with self.uow.transaction():
            entry = JournalEntry.from_recorded(
                id=command.journal_entry_id,
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
                journal_code=command.journal_code,
                reference=command.reference,
                posting_date=command.posting_date,
                lines=command.lines,
            )
            self.uow.journal_entry_repository.add(entry)
            return CreateJournalEntryResult(
                journal_entry_id=entry.id,
                status=entry.status,
                version=entry.version,
            )
