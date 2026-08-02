"""CloseAccountingPeriod use case."""

from dataclasses import dataclass

from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId
from educonnect_engine.accounting.domain.accounting_period_status import AccountingPeriodStatus
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodLifecycleRepository,
    IdempotencyRepository,
    UnitOfWork,
)


class InvalidIdempotencyKeyError(Exception):
    """Raised when idempotency key payload is invalid."""


class AccountingPeriodNotFoundError(LookupError):
    """Raised when close targets a missing accounting period."""


@dataclass(frozen=True, slots=True)
class CloseAccountingPeriodCommand:
    """Input payload for closing an accounting period."""

    accounting_period_id: AccountingPeriodId
    expected_version: int
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class CloseAccountingPeriodResult:
    """Canonical outcome returned by CloseAccountingPeriod."""

    accounting_period_id: AccountingPeriodId
    status: AccountingPeriodStatus
    version: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class CloseAccountingPeriod:
    """Application service orchestrating accounting period closure."""

    repository: AccountingPeriodLifecycleRepository
    idempotency_repository: IdempotencyRepository[CloseAccountingPeriodResult]
    uow: UnitOfWork

    def execute(self, command: CloseAccountingPeriodCommand) -> CloseAccountingPeriodResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return CloseAccountingPeriodResult(
                    accounting_period_id=stored.accounting_period_id,
                    status=stored.status,
                    version=stored.version,
                    idempotent_replay=True,
                )

            period = self.repository.get_by_id(command.accounting_period_id)
            if period is None:
                raise AccountingPeriodNotFoundError("accounting period not found")

            closed_period = period.close(expected_version=command.expected_version)
            self.repository.save(closed_period, expected_version=command.expected_version)

            result = CloseAccountingPeriodResult(
                accounting_period_id=closed_period.id,
                status=closed_period.status,
                version=closed_period.version,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result
