"""Accounting repository ports."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date
from typing import Protocol, TypeVar

from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId

from .accounting_period import AccountingPeriod
from .accounting_period_id import AccountingPeriodId
from .fiscal_year_closing import FiscalYearClosing
from .fiscal_year_closing_id import FiscalYearClosingId
from .idempotency_key import IdempotencyKey
from .journal_entry import JournalEntry
from .journal_entry_id import JournalEntryId

_ResultT = TypeVar("_ResultT")


class JournalEntryRepository(Protocol):
    """Repository contract for journal entry persistence."""

    def add(self, entry: JournalEntry) -> None:
        """Persist a newly recorded journal entry."""

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        """Load a journal entry by its identifier."""

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        """Persist a posted journal entry with optimistic version expectation."""

    def save_reversal(
        self,
        reversal_entry: JournalEntry,
        original_entry_id: JournalEntryId,
        expected_original_version: int,
    ) -> None:
        """Persist reversal atomically with version and direct-reversal uniqueness checks."""


class AccountingPeriodRepository(Protocol):
    """Repository contract exposing accounting period status."""

    def is_open(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        posting_date: date,
    ) -> bool:
        """Return whether posting date is in an open accounting period."""


class AccountingPeriodLifecycleRepository(AccountingPeriodRepository, Protocol):
    """Repository contract for accounting period lifecycle operations."""

    def get_by_id(self, accounting_period_id: AccountingPeriodId) -> AccountingPeriod | None:
        """Load an accounting period by its identifier."""

    def add(self, period: AccountingPeriod) -> None:
        """Persist a newly opened accounting period."""

    def save(self, period: AccountingPeriod, expected_version: int) -> None:
        """Persist period status transition with optimistic version expectation."""

    def has_open_period(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        """Return whether one OPEN period already exists for scope."""

    def has_overlapping_period(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        start_date: date,
        end_date: date,
    ) -> bool:
        """Return whether a period range overlaps an existing period in scope."""


class FiscalYearClosingRepository(Protocol):
    """Repository contract for fiscal year closing persistence."""

    def get_by_id(self, closing_id: FiscalYearClosingId) -> FiscalYearClosing | None:
        """Load fiscal year closing by identifier."""

    def exists_closed(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        """Return whether scope already has a persisted CLOSED fiscal year."""

    def save_closed(self, closing: FiscalYearClosing, expected_version: int) -> None:
        """Persist CLOSED fiscal year closing with optimistic version expectation."""


class FiscalYearClosingPrerequisiteRepository(Protocol):
    """Read-side contract exposing fiscal year closing prerequisites."""

    def are_all_periods_locked(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        """Return whether all accounting periods in scope are LOCKED."""

    def has_recorded_journal_entries(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        """Return whether RECORDED journal entries still exist in scope."""

    def has_posting_or_reversal_in_progress(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        """Return whether posting or reversal operations are currently in progress."""

    def has_coherent_balanced_financial_statements(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        """Return whether financial statements are coherent and balanced for scope."""


class IdempotencyRepository(Protocol[_ResultT]):
    """Repository contract for idempotent command outcomes."""

    def get(self, key: IdempotencyKey) -> _ResultT | None:
        """Retrieve a canonical stored result for the given key."""

    def save(self, key: IdempotencyKey, result: _ResultT) -> None:
        """Store a canonical result for idempotent replay."""


class UnitOfWork(Protocol):
    """Transactional boundary for grouped repository operations."""

    def transaction(self) -> AbstractContextManager[None]:
        """Open a transactional context."""
