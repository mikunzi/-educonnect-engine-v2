"""ReverseJournalEntry use case."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, final

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


class ReverseJournalEntryUnitOfWork(UnitOfWork, Protocol):
    """UnitOfWork contract required by ReverseJournalEntry handler."""

    @property
    def journal_entry_repository(self) -> JournalEntryRepository:
        """Journal entry repository bound to current transaction."""

    @property
    def accounting_period_repository(self) -> AccountingPeriodRepository:
        """Accounting period repository bound to current transaction."""

    @property
    def idempotency_repository(self) -> IdempotencyRepository[ReverseJournalEntryResult]:
        """Idempotency repository bound to current transaction."""


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
class ReverseJournalEntryHandler:
    """Transactional service orchestrating full reversal of a posted journal entry."""

    uow: ReverseJournalEntryUnitOfWork
    clock: Clock

    def execute(self, command: ReverseJournalEntryCommand) -> ReverseJournalEntryResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.uow.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return ReverseJournalEntryResult(
                    original_entry_id=stored.original_entry_id,
                    reversal_entry_id=stored.reversal_entry_id,
                    status=stored.status,
                    posted_at=stored.posted_at,
                    version=stored.version,
                    idempotent_replay=True,
                )

            original = self.uow.journal_entry_repository.get_by_id(command.original_entry_id)
            if original is None:
                raise JournalEntryNotFoundError("original journal entry not found")
            if original.status is not JournalEntryStatus.POSTED:
                raise JournalEntryNotPostedError("original journal entry must be POSTED")
            if original.version != command.expected_version:
                raise ConcurrencyConflictError("journal entry version mismatch")
            if not self.uow.accounting_period_repository.is_open(
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

            self.uow.journal_entry_repository.save_reversal(
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
            self.uow.idempotency_repository.save(command.idempotency_key, result)
            return result


@final
class _RepositoryBoundUnitOfWork(ReverseJournalEntryUnitOfWork):
    """Bind repositories to an existing UnitOfWork transaction boundary."""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        journal_entry_repository: JournalEntryRepository,
        accounting_period_repository: AccountingPeriodRepository,
        idempotency_repository: IdempotencyRepository[ReverseJournalEntryResult],
    ) -> None:
        self._uow = uow
        self._journal_entry_repository = journal_entry_repository
        self._accounting_period_repository = accounting_period_repository
        self._idempotency_repository = idempotency_repository

    @property
    def journal_entry_repository(self) -> JournalEntryRepository:
        return self._journal_entry_repository

    @property
    def accounting_period_repository(self) -> AccountingPeriodRepository:
        return self._accounting_period_repository

    @property
    def idempotency_repository(self) -> IdempotencyRepository[ReverseJournalEntryResult]:
        return self._idempotency_repository

    def transaction(self) -> AbstractContextManager[None]:
        return self._uow.transaction()


@dataclass(frozen=True, slots=True)
class ReverseJournalEntry:
    """Backward-compatible facade delegating to ReverseJournalEntryHandler."""

    repository: JournalEntryRepository
    period_repository: AccountingPeriodRepository
    idempotency_repository: IdempotencyRepository[ReverseJournalEntryResult]
    uow: UnitOfWork
    clock: Clock

    def execute(self, command: ReverseJournalEntryCommand) -> ReverseJournalEntryResult:
        bound_uow = _RepositoryBoundUnitOfWork(
            uow=self.uow,
            journal_entry_repository=self.repository,
            accounting_period_repository=self.period_repository,
            idempotency_repository=self.idempotency_repository,
        )
        return ReverseJournalEntryHandler(uow=bound_uow, clock=self.clock).execute(command)
