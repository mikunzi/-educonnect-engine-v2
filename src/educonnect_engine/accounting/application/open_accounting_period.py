"""OpenAccountingPeriod use case."""

from dataclasses import dataclass
from datetime import date

from educonnect_engine.accounting.domain.accounting_period import AccountingPeriod
from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId
from educonnect_engine.accounting.domain.accounting_period_status import AccountingPeriodStatus
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodLifecycleRepository,
    IdempotencyRepository,
    UnitOfWork,
)
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class InvalidIdempotencyKeyError(Exception):
    """Raised when idempotency key payload is invalid."""


class AccountingPeriodOpenAlreadyExistsError(Exception):
    """Raised when another OPEN period already exists in same scope."""


class AccountingPeriodOverlapError(Exception):
    """Raised when new period overlaps existing periods in same scope."""


@dataclass(frozen=True, slots=True)
class OpenAccountingPeriodCommand:
    """Input payload for opening an accounting period."""

    accounting_period_id: AccountingPeriodId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    start_date: date
    end_date: date
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class OpenAccountingPeriodResult:
    """Canonical outcome returned by OpenAccountingPeriod."""

    accounting_period_id: AccountingPeriodId
    status: AccountingPeriodStatus
    version: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class OpenAccountingPeriod:
    """Application service orchestrating accounting period opening."""

    repository: AccountingPeriodLifecycleRepository
    idempotency_repository: IdempotencyRepository[OpenAccountingPeriodResult]
    uow: UnitOfWork

    def execute(self, command: OpenAccountingPeriodCommand) -> OpenAccountingPeriodResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return OpenAccountingPeriodResult(
                    accounting_period_id=stored.accounting_period_id,
                    status=stored.status,
                    version=stored.version,
                    idempotent_replay=True,
                )

            if self.repository.has_open_period(command.legal_entity_id, command.fiscal_year):
                raise AccountingPeriodOpenAlreadyExistsError(
                    "an OPEN accounting period already exists for this scope",
                )

            if self.repository.has_overlapping_period(
                command.legal_entity_id,
                command.fiscal_year,
                command.start_date,
                command.end_date,
            ):
                raise AccountingPeriodOverlapError(
                    "accounting period overlaps an existing period in this scope",
                )

            period = AccountingPeriod(
                id=command.accounting_period_id,
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
                start_date=command.start_date,
                end_date=command.end_date,
                status=AccountingPeriodStatus.OPEN,
                version=0,
            )
            self.repository.add(period)

            result = OpenAccountingPeriodResult(
                accounting_period_id=period.id,
                status=period.status,
                version=period.version,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result
