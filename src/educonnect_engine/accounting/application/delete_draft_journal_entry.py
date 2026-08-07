"""DeleteDraftJournalEntry use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.repositories import JournalEntryRepository, UnitOfWork


class JournalEntryNotFoundError(Exception):
    """Raised when deletion targets a missing journal entry."""


class JournalEntryNotDraftError(Exception):
    """Raised when deletion targets a journal entry that is not RECORDED."""


class ConcurrencyConflictError(Exception):
    """Raised when expected version does not match current aggregate version."""


class DeleteDraftJournalEntryUnitOfWork(UnitOfWork, Protocol):
    """UnitOfWork contract required by DeleteDraftJournalEntry handler."""

    @property
    def journal_entry_repository(self) -> JournalEntryRepository:
        """Journal entry repository bound to current transaction."""


@dataclass(frozen=True, slots=True)
class DeleteDraftJournalEntryCommand:
    """Input payload for deleting one draft journal entry."""

    journal_entry_id: JournalEntryId
    expected_version: int


@dataclass(frozen=True, slots=True)
class DeleteDraftJournalEntryResult:
    """Typed output returned by DeleteDraftJournalEntry."""

    journal_entry_id: JournalEntryId
    deleted: bool


@dataclass(frozen=True, slots=True)
class DeleteDraftJournalEntryHandler:
    """Transactional service deleting one recorded journal entry."""

    uow: DeleteDraftJournalEntryUnitOfWork

    def execute(self, command: DeleteDraftJournalEntryCommand) -> DeleteDraftJournalEntryResult:
        with self.uow.transaction():
            entry = self.uow.journal_entry_repository.get_by_id(command.journal_entry_id)
            if entry is None:
                raise JournalEntryNotFoundError("journal entry not found")
            if entry.status is not JournalEntryStatus.RECORDED:
                raise JournalEntryNotDraftError("journal entry must be RECORDED")
            if entry.version != command.expected_version:
                raise ConcurrencyConflictError("journal entry version mismatch")

            self.uow.journal_entry_repository.delete_draft(
                entry_id=command.journal_entry_id,
                expected_version=command.expected_version,
            )
            return DeleteDraftJournalEntryResult(
                journal_entry_id=command.journal_entry_id,
                deleted=True,
            )
