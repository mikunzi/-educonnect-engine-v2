"""CreateYearEndSnapshot use case."""

from dataclasses import dataclass
from datetime import datetime

from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.repositories import (
    IdempotencyRepository,
    UnitOfWork,
    YearEndSnapshotPrerequisiteRepository,
    YearEndSnapshotRepository,
    YearEndSnapshotSourceRepository,
)
from educonnect_engine.accounting.domain.year_end_snapshot import YearEndSnapshot
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.shared.clock import Clock
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class InvalidIdempotencyKeyError(Exception):
    """Raised when the idempotency key payload is invalid."""


class YearEndSnapshotAlreadyExistsError(Exception):
    """Raised when a snapshot already exists for the accounting scope."""


class YearEndSnapshotFiscalYearClosedError(Exception):
    """Raised when capture is attempted after fiscal-year closing."""


class YearEndSnapshotOperationInProgressError(Exception):
    """Raised when posting or reversal is still in progress."""


class YearEndSnapshotRecordedEntriesExistError(Exception):
    """Raised when unresolved recorded journal entries exist."""


class YearEndSnapshotSourceNotFoundError(Exception):
    """Raised when no coherent projection source is available."""


@dataclass(frozen=True, slots=True)
class CreateYearEndSnapshotCommand:
    """Input payload for year-end snapshot creation."""

    snapshot_id: YearEndSnapshotId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class CreateYearEndSnapshotResult:
    """Canonical outcome returned by CreateYearEndSnapshot."""

    snapshot_id: YearEndSnapshotId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    source_version: int
    captured_at: datetime
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class CreateYearEndSnapshot:
    """Capture one immutable and coherent year-end accounting state."""

    source_repository: YearEndSnapshotSourceRepository
    snapshot_repository: YearEndSnapshotRepository
    prerequisites: YearEndSnapshotPrerequisiteRepository
    idempotency_repository: IdempotencyRepository[CreateYearEndSnapshotResult]
    uow: UnitOfWork
    clock: Clock

    def execute(self, command: CreateYearEndSnapshotCommand) -> CreateYearEndSnapshotResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return CreateYearEndSnapshotResult(
                    snapshot_id=stored.snapshot_id,
                    legal_entity_id=stored.legal_entity_id,
                    fiscal_year=stored.fiscal_year,
                    source_version=stored.source_version,
                    captured_at=stored.captured_at,
                    idempotent_replay=True,
                )

            existing = self.snapshot_repository.get_by_scope(
                command.legal_entity_id,
                command.fiscal_year,
            )
            if existing is not None:
                raise YearEndSnapshotAlreadyExistsError(
                    "year-end snapshot already exists for accounting scope",
                )
            if self.prerequisites.is_fiscal_year_closed(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise YearEndSnapshotFiscalYearClosedError("fiscal year is already closed")
            if self.prerequisites.has_recorded_journal_entries(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise YearEndSnapshotRecordedEntriesExistError(
                    "recorded journal entries must be resolved before capture",
                )
            if self.prerequisites.has_posting_or_reversal_in_progress(
                command.legal_entity_id,
                command.fiscal_year,
            ):
                raise YearEndSnapshotOperationInProgressError(
                    "posting or reversal must not be in progress during capture",
                )

            source = self.source_repository.get_consistent_source(
                command.legal_entity_id,
                command.fiscal_year,
            )
            if source is None:
                raise YearEndSnapshotSourceNotFoundError(
                    "coherent year-end snapshot source was not found",
                )

            snapshot = YearEndSnapshot.capture(
                id=command.snapshot_id,
                trial_balance=source.trial_balance,
                financial_statements=source.financial_statements,
                source_version=source.source_version,
                captured_at=self.clock.now_utc(),
            )
            self.snapshot_repository.add(
                snapshot,
                expected_source_version=source.source_version,
            )
            result = CreateYearEndSnapshotResult(
                snapshot_id=snapshot.id,
                legal_entity_id=snapshot.legal_entity_id,
                fiscal_year=snapshot.fiscal_year,
                source_version=snapshot.source_version,
                captured_at=snapshot.captured_at,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result