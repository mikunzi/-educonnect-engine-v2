"""PostJournalEntry use case."""

from dataclasses import dataclass
from datetime import datetime

from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodRepository,
    IdempotencyRepository,
    JournalEntryRepository,
    UnitOfWork,
)
from educonnect_engine.shared.clock import Clock


class JournalEntryNotFoundError(Exception):
    """Raised when posting targets a missing journal entry."""


class JournalEntryAlreadyPostedError(Exception):
    """Raised when posting targets an entry already posted."""


class AccountingPeriodClosedError(Exception):
    """Raised when posting date falls in a closed period."""


class ConcurrencyConflictError(Exception):
    """Raised when expected version does not match current aggregate version."""


class InvalidIdempotencyKeyError(Exception):
    """Raised when idempotency key payload is invalid."""


@dataclass(frozen=True, slots=True)
class PostJournalEntryCommand:
    """Input payload for posting a recorded journal entry."""

    journal_entry_id: JournalEntryId
    expected_version: int
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class PostJournalEntryResult:
    """Canonical outcome returned by PostJournalEntry."""

    entry_id: JournalEntryId
    status: JournalEntryStatus
    posted_at: datetime
    version: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class PostJournalEntry:
    """Application service orchestrating RECORDED to POSTED transition."""

    repository: JournalEntryRepository
    period_repository: AccountingPeriodRepository
    idempotency_repository: IdempotencyRepository[PostJournalEntryResult]
    uow: UnitOfWork
    clock: Clock

    def execute(self, command: PostJournalEntryCommand) -> PostJournalEntryResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return PostJournalEntryResult(
                    entry_id=stored.entry_id,
                    status=stored.status,
                    posted_at=stored.posted_at,
                    version=stored.version,
                    idempotent_replay=True,
                )

            entry = self.repository.get_by_id(command.journal_entry_id)
            if entry is None:
                raise JournalEntryNotFoundError("journal entry not found")
            if entry.status is JournalEntryStatus.POSTED:
                raise JournalEntryAlreadyPostedError("journal entry is already posted")
            if entry.version != command.expected_version:
                raise ConcurrencyConflictError("journal entry version mismatch")
            if not self.period_repository.is_open(
                legal_entity_id=entry.legal_entity_id,
                fiscal_year=entry.fiscal_year,
                posting_date=entry.posting_date,
            ):
                raise AccountingPeriodClosedError("accounting period is closed")

            posted_entry = entry.post(posted_at=self.clock.now_utc())
            self.repository.save_posted(posted_entry, expected_version=command.expected_version)

            posted_at = posted_entry.posted_at
            if posted_at is None:
                raise RuntimeError("posted journal entry must define posted_at")

            result = PostJournalEntryResult(
                entry_id=posted_entry.id,
                status=posted_entry.status,
                posted_at=posted_at,
                version=posted_entry.version,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result
