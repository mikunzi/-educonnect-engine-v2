"""ReverseJournalEntry use case."""

from dataclasses import dataclass
from datetime import date, datetime

from educonnect_engine.accounting.domain.correction_reason import CorrectionReason
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
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference


class JournalEntryNotFoundError(Exception):
    """Raised when reversal targets a missing journal entry."""


class JournalEntryNotPostedError(Exception):
    """Raised when reversal targets an entry that is not POSTED."""


class AccountingPeriodClosedError(Exception):
    """Raised when reversal date falls in a closed period."""


class ConcurrencyConflictError(Exception):
    """Raised when expected version does not match current aggregate version."""


class InvalidIdempotencyKeyError(Exception):
    """Raised when idempotency key payload is invalid."""


@dataclass(frozen=True, slots=True)
class ReverseJournalEntryCommand:
    """Input payload for reversing a posted journal entry."""

    original_entry_id: JournalEntryId
    expected_version: int
    idempotency_key: IdempotencyKey
    reversal_entry_id: JournalEntryId
    reversal_fiscal_year: FiscalYear
    reversal_journal_code: JournalCode
    reversal_reference: JournalReference
    reversal_date: date
    correction_reason: CorrectionReason


@dataclass(frozen=True, slots=True)
class ReverseJournalEntryResult:
    """Canonical outcome returned by ReverseJournalEntry."""

    original_entry_id: JournalEntryId
    reversal_entry_id: JournalEntryId
    status: JournalEntryStatus
    posted_at: datetime
    version: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class ReverseJournalEntry:
    """Application service orchestrating full reversal of a posted journal entry."""

    repository: JournalEntryRepository
    period_repository: AccountingPeriodRepository
    idempotency_repository: IdempotencyRepository[ReverseJournalEntryResult]
    uow: UnitOfWork
    clock: Clock

    def execute(self, command: ReverseJournalEntryCommand) -> ReverseJournalEntryResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return ReverseJournalEntryResult(
                    original_entry_id=stored.original_entry_id,
                    reversal_entry_id=stored.reversal_entry_id,
                    status=stored.status,
                    posted_at=stored.posted_at,
                    version=stored.version,
                    idempotent_replay=True,
                )

            original = self.repository.get_by_id(command.original_entry_id)
            if original is None:
                raise JournalEntryNotFoundError("original journal entry not found")
            if original.status is not JournalEntryStatus.POSTED:
                raise JournalEntryNotPostedError("original journal entry must be POSTED")
            if original.version != command.expected_version:
                raise ConcurrencyConflictError("journal entry version mismatch")
            if not self.period_repository.is_open(
                legal_entity_id=original.legal_entity_id,
                fiscal_year=command.reversal_fiscal_year,
                posting_date=command.reversal_date,
            ):
                raise AccountingPeriodClosedError("accounting period is closed")

            reversal_recorded = original.build_reversal(
                reversal_entry_id=command.reversal_entry_id,
                reversal_fiscal_year=command.reversal_fiscal_year,
                reversal_journal_code=command.reversal_journal_code,
                reversal_reference=command.reversal_reference,
                reversal_date=command.reversal_date,
                correction_reason=command.correction_reason,
            )
            reversal_posted = reversal_recorded.post(posted_at=self.clock.now_utc())

            self.repository.save_reversal(
                reversal_entry=reversal_posted,
                original_entry_id=command.original_entry_id,
                expected_original_version=command.expected_version,
            )

            posted_at = reversal_posted.posted_at
            if posted_at is None:
                raise RuntimeError("posted reversal entry must define posted_at")

            result = ReverseJournalEntryResult(
                original_entry_id=command.original_entry_id,
                reversal_entry_id=reversal_posted.id,
                status=reversal_posted.status,
                posted_at=posted_at,
                version=reversal_posted.version,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result
