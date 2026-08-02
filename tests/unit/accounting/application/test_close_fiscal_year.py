"""Unit tests for CloseFiscalYear use case."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from educonnect_engine.accounting.application.close_fiscal_year import (
    CloseFiscalYear,
    CloseFiscalYearCommand,
    CloseFiscalYearResult,
    FiscalYearAlreadyClosedError,
    FiscalYearFinancialStatementsNotReadyError,
    FiscalYearHasRecordedEntriesError,
    FiscalYearPostingOrReverseInProgressError,
    FiscalYearPrerequisitesNotLockedError,
    InvalidIdempotencyKeyError,
)
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


@dataclass
class _FakeFiscalYearClosingRepository(FiscalYearClosingRepository):
    closings: dict[FiscalYearClosingId, FiscalYearClosing]
    closed_scope: set[tuple[LegalEntityId, FiscalYear]]

    def get_by_id(self, closing_id: FiscalYearClosingId) -> FiscalYearClosing | None:
        return self.closings.get(closing_id)

    def exists_closed(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        return (legal_entity_id, fiscal_year) in self.closed_scope

    def save_closed(self, closing: FiscalYearClosing, expected_version: int) -> None:
        if closing.version != expected_version + 1:
            raise ValueError("invalid close version progression")
        self.closings[closing.id] = closing
        self.closed_scope.add((closing.legal_entity_id, closing.fiscal_year))


@dataclass
class _FakePrerequisiteRepository(FiscalYearClosingPrerequisiteRepository):
    all_periods_locked: bool = True
    has_recorded_entries: bool = False
    has_posting_or_reverse_in_progress: bool = False
    financial_statements_ready: bool = True

    def are_all_periods_locked(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.all_periods_locked

    def has_recorded_journal_entries(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.has_recorded_entries

    def has_posting_or_reversal_in_progress(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.has_posting_or_reverse_in_progress

    def has_coherent_balanced_financial_statements(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.financial_statements_ready


@dataclass
class _FakeIdempotencyRepository(IdempotencyRepository[CloseFiscalYearResult]):
    values: dict[IdempotencyKey, CloseFiscalYearResult]

    def get(self, key: IdempotencyKey) -> CloseFiscalYearResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: CloseFiscalYearResult) -> None:
        self.values[key] = result


@dataclass
class _FakeUnitOfWork(UnitOfWork):
    entered: int = 0

    @contextmanager
    def transaction(self):
        self.entered += 1
        yield


@dataclass(frozen=True, slots=True)
class _FixedClock(Clock):
    fixed_now: datetime = datetime(2026, 12, 31, 23, 59, tzinfo=UTC)

    def now_utc(self) -> datetime:
        return self.fixed_now


def _command() -> CloseFiscalYearCommand:
    return CloseFiscalYearCommand(
        closing_id=FiscalYearClosingId(value="FYC-2026"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        idempotency_key=IdempotencyKey(value="close-fy-2026"),
    )


def test_close_fiscal_year_first_processing_returns_canonical_result() -> None:
    repository = _FakeFiscalYearClosingRepository(closings={}, closed_scope=set())
    prerequisites = _FakePrerequisiteRepository()
    idempotency_repository = _FakeIdempotencyRepository(values={})
    uow = _FakeUnitOfWork()
    use_case = CloseFiscalYear(
        repository=repository,
        prerequisites=prerequisites,
        idempotency_repository=idempotency_repository,
        uow=uow,
        clock=_FixedClock(),
    )

    result = use_case.execute(_command())

    assert result.closing_id == FiscalYearClosingId(value="FYC-2026")
    assert result.status is FiscalYearClosingStatus.CLOSED
    assert result.version == 1
    assert result.closing_timestamp == ClosingTimestamp(
        value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
    )
    assert result.idempotent_replay is False
    assert uow.entered == 1


def test_close_fiscal_year_replay_returns_copy_with_replay_flag() -> None:
    canonical = CloseFiscalYearResult(
        closing_id=FiscalYearClosingId(value="FYC-2026"),
        status=FiscalYearClosingStatus.CLOSED,
        closing_timestamp=ClosingTimestamp(value=datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
        version=1,
        idempotent_replay=False,
    )
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope=set()),
        prerequisites=_FakePrerequisiteRepository(),
        idempotency_repository=_FakeIdempotencyRepository(
            values={IdempotencyKey(value="close-fy-2026"): canonical},
        ),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    replay = use_case.execute(_command())

    assert replay.closing_id == canonical.closing_id
    assert replay.status is canonical.status
    assert replay.closing_timestamp == canonical.closing_timestamp
    assert replay.version == canonical.version
    assert replay.idempotent_replay is True


def test_close_fiscal_year_rejects_existing_closed_scope() -> None:
    scope = (LegalEntityId(value="entity-01"), FiscalYear(value=2026))
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope={scope}),
        prerequisites=_FakePrerequisiteRepository(),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(FiscalYearAlreadyClosedError):
        use_case.execute(_command())


def test_close_fiscal_year_rejects_unlocked_periods() -> None:
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope=set()),
        prerequisites=_FakePrerequisiteRepository(all_periods_locked=False),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(FiscalYearPrerequisitesNotLockedError):
        use_case.execute(_command())


def test_close_fiscal_year_rejects_recorded_entries() -> None:
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope=set()),
        prerequisites=_FakePrerequisiteRepository(has_recorded_entries=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(FiscalYearHasRecordedEntriesError):
        use_case.execute(_command())


def test_close_fiscal_year_rejects_posting_or_reverse_in_progress() -> None:
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope=set()),
        prerequisites=_FakePrerequisiteRepository(has_posting_or_reverse_in_progress=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(FiscalYearPostingOrReverseInProgressError):
        use_case.execute(_command())


def test_close_fiscal_year_rejects_financial_statements_not_ready() -> None:
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope=set()),
        prerequisites=_FakePrerequisiteRepository(financial_statements_ready=False),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(FiscalYearFinancialStatementsNotReadyError):
        use_case.execute(_command())


def test_close_fiscal_year_rejects_invalid_idempotency_key() -> None:
    use_case = CloseFiscalYear(
        repository=_FakeFiscalYearClosingRepository(closings={}, closed_scope=set()),
        prerequisites=_FakePrerequisiteRepository(),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            CloseFiscalYearCommand(
                closing_id=FiscalYearClosingId(value="FYC-2026"),
                legal_entity_id=LegalEntityId(value="entity-01"),
                fiscal_year=FiscalYear(value=2026),
                idempotency_key="close-fy-2026",  # type: ignore[arg-type]
            ),
        )
