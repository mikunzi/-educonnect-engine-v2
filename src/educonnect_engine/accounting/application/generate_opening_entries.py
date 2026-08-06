"""GenerateOpeningEntries use case."""

from dataclasses import dataclass
from datetime import date

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.generate_opening_entries_service import (
    GenerateOpeningEntriesService,
)
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.opening_entry_status import OpeningEntryStatus
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodRepository,
    FiscalYearClosingRepository,
    IdempotencyRepository,
    OpeningEntryRepository,
    UnitOfWork,
    YearEndSnapshotRepository,
)
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference


class InvalidIdempotencyKeyError(Exception):
    """Raised when the idempotency key payload is invalid."""


class GenerateOpeningEntriesAlreadyExistsError(Exception):
    """Raised when a snapshot already has an opening entry."""


class OpeningEntriesSourceFiscalYearNotClosedError(Exception):
    """Raised when the source fiscal year has not been closed."""


class OpeningEntriesTargetPeriodNotOpenError(Exception):
    """Raised when the target posting date is not in an open period."""


class YearEndSnapshotNotFoundError(Exception):
    """Raised when the requested year-end snapshot does not exist."""


@dataclass(frozen=True, slots=True)
class GenerateOpeningEntriesCommand:
    """Input payload for opening-entry generation."""

    source_snapshot_id: YearEndSnapshotId
    journal_entry_id: JournalEntryId
    target_fiscal_year: FiscalYear
    journal_code: JournalCode
    reference: JournalReference
    posting_date: date
    retained_earnings_account_number: AccountNumber
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class GenerateOpeningEntriesResult:
    """Canonical outcome returned by GenerateOpeningEntries."""

    source_snapshot_id: YearEndSnapshotId
    journal_entry_id: JournalEntryId
    target_fiscal_year: FiscalYear
    status: OpeningEntryStatus
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class GenerateOpeningEntries:
    """Orchestrate opening-entry prerequisites and persistence."""

    snapshot_repository: YearEndSnapshotRepository
    opening_entry_repository: OpeningEntryRepository
    fiscal_year_closing_repository: FiscalYearClosingRepository
    accounting_period_repository: AccountingPeriodRepository
    idempotency_repository: IdempotencyRepository[GenerateOpeningEntriesResult]
    uow: UnitOfWork
    generator: GenerateOpeningEntriesService

    def execute(self, command: GenerateOpeningEntriesCommand) -> GenerateOpeningEntriesResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return GenerateOpeningEntriesResult(
                    source_snapshot_id=stored.source_snapshot_id,
                    journal_entry_id=stored.journal_entry_id,
                    target_fiscal_year=stored.target_fiscal_year,
                    status=stored.status,
                    idempotent_replay=True,
                )

            snapshot = self.snapshot_repository.get_by_id(command.source_snapshot_id)
            if snapshot is None:
                raise YearEndSnapshotNotFoundError("year-end snapshot was not found")
            if self.opening_entry_repository.exists_for_snapshot(snapshot.id):
                raise GenerateOpeningEntriesAlreadyExistsError(
                    "opening entry already exists for year-end snapshot",
                )
            if not self.fiscal_year_closing_repository.exists_closed(
                snapshot.legal_entity_id,
                snapshot.fiscal_year,
            ):
                raise OpeningEntriesSourceFiscalYearNotClosedError(
                    "source fiscal year must be closed before opening-entry generation",
                )
            if not self.accounting_period_repository.is_open(
                snapshot.legal_entity_id,
                command.target_fiscal_year,
                command.posting_date,
            ):
                raise OpeningEntriesTargetPeriodNotOpenError(
                    "target posting date must belong to an open accounting period",
                )

            opening_entry = self.generator.generate(
                snapshot=snapshot,
                journal_entry_id=command.journal_entry_id,
                target_fiscal_year=command.target_fiscal_year,
                journal_code=command.journal_code,
                reference=command.reference,
                posting_date=command.posting_date,
                retained_earnings_account_number=command.retained_earnings_account_number,
            )
            self.opening_entry_repository.add(opening_entry)
            result = GenerateOpeningEntriesResult(
                source_snapshot_id=opening_entry.source_snapshot_id,
                journal_entry_id=opening_entry.journal_entry.id,
                target_fiscal_year=opening_entry.target_fiscal_year,
                status=opening_entry.status,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result