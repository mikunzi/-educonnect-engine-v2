"""Unit tests for LockAccountingPeriod use case."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

import pytest

from educonnect_engine.accounting.application.lock_accounting_period import (
    InvalidIdempotencyKeyError,
    LockAccountingPeriod,
    LockAccountingPeriodCommand,
    LockAccountingPeriodResult,
)
from educonnect_engine.accounting.domain.accounting_period import (
    AccountingPeriod,
    AccountingPeriodTransitionError,
)
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


@dataclass
class _FakeAccountingPeriodLifecycleRepository(AccountingPeriodLifecycleRepository):
    periods: dict[AccountingPeriodId, AccountingPeriod]
    save_calls: int = 0

    def is_open(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        posting_date: date,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year, posting_date)
        return False

    def get_by_id(self, accounting_period_id: AccountingPeriodId) -> AccountingPeriod | None:
        return self.periods.get(accounting_period_id)

    def add(self, period: AccountingPeriod) -> None:
        self.periods[period.id] = period

    def save(self, period: AccountingPeriod, expected_version: int) -> None:
        self.save_calls += 1
        self.periods[period.id] = period
        _ = expected_version

    def has_open_period(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return False

    def has_overlapping_period(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        start_date: date,
        end_date: date,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year, start_date, end_date)
        return False


@dataclass
class _FakeIdempotencyRepository(IdempotencyRepository[LockAccountingPeriodResult]):
    values: dict[IdempotencyKey, LockAccountingPeriodResult]

    def get(self, key: IdempotencyKey) -> LockAccountingPeriodResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: LockAccountingPeriodResult) -> None:
        self.values[key] = result


@dataclass
class _FakeUnitOfWork(UnitOfWork):
    @contextmanager
    def transaction(self):
        yield


def _closed_period() -> AccountingPeriod:
    return AccountingPeriod(
        id=AccountingPeriodId(value="PER-2026-01"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=AccountingPeriodStatus.CLOSED,
        version=1,
    )


def test_lock_accounting_period_first_processing_returns_canonical_result() -> None:
    period = _closed_period()
    repository = _FakeAccountingPeriodLifecycleRepository(periods={period.id: period})
    idempotency_repository = _FakeIdempotencyRepository(values={})
    use_case = LockAccountingPeriod(
        repository=repository,
        idempotency_repository=idempotency_repository,
        uow=_FakeUnitOfWork(),
    )

    result = use_case.execute(
        LockAccountingPeriodCommand(
            accounting_period_id=period.id,
            expected_version=1,
            idempotency_key=IdempotencyKey(value="lock-period-2026-01"),
        ),
    )

    assert result.accounting_period_id == period.id
    assert result.status is AccountingPeriodStatus.LOCKED
    assert result.version == 2
    assert result.idempotent_replay is False
    assert repository.save_calls == 1


def test_lock_accounting_period_replay_returns_copy_with_replay_flag() -> None:
    canonical = LockAccountingPeriodResult(
        accounting_period_id=AccountingPeriodId(value="PER-2026-01"),
        status=AccountingPeriodStatus.LOCKED,
        version=2,
        idempotent_replay=False,
    )
    use_case = LockAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={}),
        idempotency_repository=_FakeIdempotencyRepository(
            values={IdempotencyKey(value="lock-period-2026-01"): canonical},
        ),
        uow=_FakeUnitOfWork(),
    )

    replay = use_case.execute(
        LockAccountingPeriodCommand(
            accounting_period_id=AccountingPeriodId(value="PER-2026-01"),
            expected_version=2,
            idempotency_key=IdempotencyKey(value="lock-period-2026-01"),
        ),
    )

    assert replay.accounting_period_id == canonical.accounting_period_id
    assert replay.status is canonical.status
    assert replay.version == canonical.version
    assert replay.idempotent_replay is True


def test_lock_accounting_period_raises_not_found() -> None:
    use_case = LockAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={}),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
    )

    with pytest.raises(LookupError):
        use_case.execute(
            LockAccountingPeriodCommand(
                accounting_period_id=AccountingPeriodId(value="PER-2026-01"),
                expected_version=1,
                idempotency_key=IdempotencyKey(value="lock-period-2026-01"),
            ),
        )


def test_lock_accounting_period_raises_invalid_transition() -> None:
    open_period = AccountingPeriod(
        id=AccountingPeriodId(value="PER-2026-01"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=AccountingPeriodStatus.OPEN,
        version=0,
    )
    use_case = LockAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={open_period.id: open_period}),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
    )

    with pytest.raises(AccountingPeriodTransitionError):
        use_case.execute(
            LockAccountingPeriodCommand(
                accounting_period_id=open_period.id,
                expected_version=0,
                idempotency_key=IdempotencyKey(value="lock-period-2026-01"),
            ),
        )


def test_lock_accounting_period_raises_invalid_idempotency_key() -> None:
    period = _closed_period()
    use_case = LockAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={period.id: period}),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
    )

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            LockAccountingPeriodCommand(
                accounting_period_id=period.id,
                expected_version=1,
                idempotency_key="lock-period-2026-01",  # type: ignore[arg-type]
            ),
        )
