"""Unit tests for OpenAccountingPeriod use case."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

import pytest

from educonnect_engine.accounting.application.open_accounting_period import (
    AccountingPeriodOpenAlreadyExistsError,
    AccountingPeriodOverlapError,
    InvalidIdempotencyKeyError,
    OpenAccountingPeriod,
    OpenAccountingPeriodCommand,
    OpenAccountingPeriodResult,
)
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


@dataclass
class _FakeAccountingPeriodLifecycleRepository(AccountingPeriodLifecycleRepository):
    periods: dict[AccountingPeriodId, AccountingPeriod]
    has_open_flag: bool = False
    has_overlap_flag: bool = False
    add_calls: int = 0

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
        self.add_calls += 1
        self.periods[period.id] = period

    def save(self, period: AccountingPeriod, expected_version: int) -> None:
        _ = (period, expected_version)

    def has_open_period(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.has_open_flag

    def has_overlapping_period(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        start_date: date,
        end_date: date,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year, start_date, end_date)
        return self.has_overlap_flag


@dataclass
class _FakeIdempotencyRepository(IdempotencyRepository[OpenAccountingPeriodResult]):
    values: dict[IdempotencyKey, OpenAccountingPeriodResult]

    def get(self, key: IdempotencyKey) -> OpenAccountingPeriodResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: OpenAccountingPeriodResult) -> None:
        self.values[key] = result


@dataclass
class _FakeUnitOfWork(UnitOfWork):
    entered: int = 0

    @contextmanager
    def transaction(self):
        self.entered += 1
        yield


def _command() -> OpenAccountingPeriodCommand:
    return OpenAccountingPeriodCommand(
        accounting_period_id=AccountingPeriodId(value="PER-2026-01"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        idempotency_key=IdempotencyKey(value="open-period-2026-01"),
    )


def test_open_accounting_period_first_processing_returns_canonical_result() -> None:
    repository = _FakeAccountingPeriodLifecycleRepository(periods={})
    idempotency_repository = _FakeIdempotencyRepository(values={})
    use_case = OpenAccountingPeriod(
        repository=repository,
        idempotency_repository=idempotency_repository,
        uow=_FakeUnitOfWork(),
    )

    result = use_case.execute(_command())

    assert result.accounting_period_id == AccountingPeriodId(value="PER-2026-01")
    assert result.status is AccountingPeriodStatus.OPEN
    assert result.version == 0
    assert result.idempotent_replay is False
    assert repository.add_calls == 1


def test_open_accounting_period_replay_returns_copy_with_replay_flag() -> None:
    canonical = OpenAccountingPeriodResult(
        accounting_period_id=AccountingPeriodId(value="PER-2026-01"),
        status=AccountingPeriodStatus.OPEN,
        version=0,
        idempotent_replay=False,
    )
    use_case = OpenAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={}),
        idempotency_repository=_FakeIdempotencyRepository(
            values={IdempotencyKey(value="open-period-2026-01"): canonical},
        ),
        uow=_FakeUnitOfWork(),
    )

    replay = use_case.execute(_command())

    assert replay.accounting_period_id == canonical.accounting_period_id
    assert replay.status is canonical.status
    assert replay.version == canonical.version
    assert replay.idempotent_replay is True


def test_open_accounting_period_rejects_existing_open_period() -> None:
    use_case = OpenAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={}, has_open_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
    )

    with pytest.raises(AccountingPeriodOpenAlreadyExistsError):
        use_case.execute(_command())


def test_open_accounting_period_rejects_overlapping_period() -> None:
    use_case = OpenAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={}, has_overlap_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
    )

    with pytest.raises(AccountingPeriodOverlapError):
        use_case.execute(_command())


def test_open_accounting_period_rejects_invalid_idempotency_key() -> None:
    use_case = OpenAccountingPeriod(
        repository=_FakeAccountingPeriodLifecycleRepository(periods={}),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
    )

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            OpenAccountingPeriodCommand(
                accounting_period_id=AccountingPeriodId(value="PER-2026-01"),
                legal_entity_id=LegalEntityId(value="entity-01"),
                fiscal_year=FiscalYear(value=2026),
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                idempotency_key="open-period-2026-01",  # type: ignore[arg-type]
            ),
        )
