"""CloseFiscalYear use case."""

from dataclasses import dataclass

from educonnect_engine.accounting.domain.closing_timestamp import ClosingTimestamp
from educonnect_engine.accounting.domain.fiscal_year_closing import FiscalYearClosing
from educonnect_engine.accounting.domain.fiscal_year_closing_id import FiscalYearClosingId
from educonnect_engine.accounting.domain.fiscal_year_closing_status import FiscalYearClosingStatus
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.repositories import (
    FiscalYearClosingPrerequisiteRepository,
    FiscalYearClosingRepository,
    IdempotencyRepository,
    UnitOfWork,
)
from educonnect_engine.shared.clock import Clock
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class InvalidIdempotencyKeyError(Exception):
    """Raised when idempotency key payload is invalid."""


class FiscalYearAlreadyClosedError(Exception):
    """Raised when fiscal year closing already exists for scope."""


class FiscalYearPrerequisitesNotLockedError(Exception):
    """Raised when not all accounting periods are locked."""


class FiscalYearHasRecordedEntriesError(Exception):
    """Raised when recorded journal entries still exist in fiscal year scope."""


class FiscalYearPostingOrReverseInProgressError(Exception):
    """Raised when posting or reversal operation is still in progress."""


class FiscalYearFinancialStatementsNotReadyError(Exception):
    """Raised when financial statements are not coherent and balanced."""


@dataclass(frozen=True, slots=True)
class CloseFiscalYearCommand:
    """Input payload for fiscal year closing."""

    closing_id: FiscalYearClosingId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class CloseFiscalYearResult:
    """Canonical outcome returned by CloseFiscalYear."""

    closing_id: FiscalYearClosingId
    status: FiscalYearClosingStatus
    closing_timestamp: ClosingTimestamp
    version: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class CloseFiscalYear:
    """Application service orchestrating fiscal year closing."""

    repository: FiscalYearClosingRepository
    prerequisites: FiscalYearClosingPrerequisiteRepository
    idempotency_repository: IdempotencyRepository[CloseFiscalYearResult]
    uow: UnitOfWork
    clock: Clock

    def execute(self, command: CloseFiscalYearCommand) -> CloseFiscalYearResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return CloseFiscalYearResult(
                    closing_id=stored.closing_id,
                    status=stored.status,
                    closing_timestamp=stored.closing_timestamp,
                    version=stored.version,
                    idempotent_replay=True,
                )

            if self.repository.exists_closed(command.legal_entity_id, command.fiscal_year):
                raise FiscalYearAlreadyClosedError("fiscal year is already closed")
            if not self.prerequisites.are_all_periods_locked(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise FiscalYearPrerequisitesNotLockedError(
                    "all accounting periods must be LOCKED before fiscal year closing",
                )
            if self.prerequisites.has_recorded_journal_entries(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise FiscalYearHasRecordedEntriesError(
                    "recorded journal entries must be resolved before fiscal year closing",
                )
            if self.prerequisites.has_posting_or_reversal_in_progress(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise FiscalYearPostingOrReverseInProgressError(
                    "posting or reversal must not be in progress during fiscal year closing",
                )
            if not self.prerequisites.has_coherent_balanced_financial_statements(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise FiscalYearFinancialStatementsNotReadyError(
                    "financial statements must be coherent and balanced before fiscal year closing",
                )

            open_closing = FiscalYearClosing.open(
                id=command.closing_id,
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
            )
            closed_closing = open_closing.close(
                timestamp=ClosingTimestamp(value=self.clock.now_utc()),
                expected_version=0,
            )
            self.repository.save_closed(closed_closing, expected_version=0)
            assert closed_closing.closing_timestamp is not None

            result = CloseFiscalYearResult(
                closing_id=closed_closing.id,
                status=closed_closing.status,
                closing_timestamp=closed_closing.closing_timestamp,
                version=closed_closing.version,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result
