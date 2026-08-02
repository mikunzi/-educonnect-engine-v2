"""LockAccountingPeriod use case."""

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
    """Raised when lock targets a missing accounting period."""


@dataclass(frozen=True, slots=True)
class LockAccountingPeriodCommand:
    """Input payload for locking an accounting period."""

    accounting_period_id: AccountingPeriodId
    expected_version: int
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class LockAccountingPeriodResult:
    """Canonical outcome returned by LockAccountingPeriod."""

    accounting_period_id: AccountingPeriodId
    status: AccountingPeriodStatus
    version: int
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class LockAccountingPeriod:
    """Application service orchestrating definitive accounting period lock."""

    repository: AccountingPeriodLifecycleRepository
    idempotency_repository: IdempotencyRepository[LockAccountingPeriodResult]
    uow: UnitOfWork

    def execute(self, command: LockAccountingPeriodCommand) -> LockAccountingPeriodResult:
        if not isinstance(command.idempotency_key, IdempotencyKey):
            raise InvalidIdempotencyKeyError("idempotency key must be an IdempotencyKey")

        with self.uow.transaction():
            stored = self.idempotency_repository.get(command.idempotency_key)
            if stored is not None:
                return LockAccountingPeriodResult(
                    accounting_period_id=stored.accounting_period_id,
                    status=stored.status,
                    version=stored.version,
                    idempotent_replay=True,
                )

            period = self.repository.get_by_id(command.accounting_period_id)
            if period is None:
                raise AccountingPeriodNotFoundError("accounting period not found")

            locked_period = period.lock(expected_version=command.expected_version)
            self.repository.save(locked_period, expected_version=command.expected_version)

            result = LockAccountingPeriodResult(
                accounting_period_id=locked_period.id,
                status=locked_period.status,
                version=locked_period.version,
                idempotent_replay=False,
            )
            self.idempotency_repository.save(command.idempotency_key, result)
            return result
