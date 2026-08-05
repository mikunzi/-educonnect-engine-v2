"""Unit tests for CreateYearEndSnapshot use case."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.application.create_year_end_snapshot import (
    CreateYearEndSnapshot,
    CreateYearEndSnapshotCommand,
    CreateYearEndSnapshotResult,
    InvalidIdempotencyKeyError,
    YearEndSnapshotAlreadyExistsError,
    YearEndSnapshotFiscalYearClosedError,
    YearEndSnapshotOperationInProgressError,
    YearEndSnapshotRecordedEntriesExistError,
    YearEndSnapshotSourceNotFoundError,
)
from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_section import BalanceSheetSection
from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.financial_statements import FinancialStatements
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_section import IncomeStatementSection
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.repositories import (
    IdempotencyRepository,
    UnitOfWork,
    YearEndSnapshotPrerequisiteRepository,
    YearEndSnapshotRepository,
    YearEndSnapshotSourceRepository,
)
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.year_end_snapshot import YearEndSnapshot
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.accounting.domain.year_end_snapshot_source import YearEndSnapshotSource
from educonnect_engine.shared.clock import Clock
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _FakeSourceRepository(YearEndSnapshotSourceRepository):
    source: YearEndSnapshotSource | None
    calls: int = 0

    def get_consistent_source(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> YearEndSnapshotSource | None:
        _ = (legal_entity_id, fiscal_year)
        self.calls += 1
        return self.source


@dataclass
class _FakeSnapshotRepository(YearEndSnapshotRepository):
    snapshots: dict[YearEndSnapshotId, YearEndSnapshot]
    scoped_snapshots: dict[tuple[LegalEntityId, FiscalYear], YearEndSnapshot]
    add_calls: list[tuple[YearEndSnapshot, int]]

    def get_by_id(self, snapshot_id: YearEndSnapshotId) -> YearEndSnapshot | None:
        return self.snapshots.get(snapshot_id)

    def get_by_scope(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> YearEndSnapshot | None:
        return self.scoped_snapshots.get((legal_entity_id, fiscal_year))

    def add(self, snapshot: YearEndSnapshot, expected_source_version: int) -> None:
        self.add_calls.append((snapshot, expected_source_version))
        self.snapshots[snapshot.id] = snapshot
        self.scoped_snapshots[(snapshot.legal_entity_id, snapshot.fiscal_year)] = snapshot


@dataclass
class _FakePrerequisiteRepository(YearEndSnapshotPrerequisiteRepository):
    recorded_entries: bool = False
    operation_in_progress: bool = False
    fiscal_year_closed: bool = False

    def has_recorded_journal_entries(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.recorded_entries

    def has_posting_or_reversal_in_progress(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.operation_in_progress

    def is_fiscal_year_closed(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.fiscal_year_closed


@dataclass
class _FakeIdempotencyRepository(IdempotencyRepository[CreateYearEndSnapshotResult]):
    values: dict[IdempotencyKey, CreateYearEndSnapshotResult]

    def get(self, key: IdempotencyKey) -> CreateYearEndSnapshotResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: CreateYearEndSnapshotResult) -> None:
        self.values[key] = result


@dataclass
class _FakeUnitOfWork(UnitOfWork):
    entered: int = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.entered += 1
        yield


@dataclass(frozen=True, slots=True)
class _FixedClock(Clock):
    fixed_now: datetime = datetime(2026, 12, 31, 23, 0, tzinfo=UTC)

    def now_utc(self) -> datetime:
        return self.fixed_now


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _financial_statements(scope: LedgerScope) -> FinancialStatements:
    zero = Money(amount=Decimal("0"), currency=scope.currency)
    return FinancialStatements(
        balance_sheet=BalanceSheet(
            scope=scope,
            assets=BalanceSheetSection(
                classification=AccountClassification.ASSET,
                currency=scope.currency,
                lines=(),
            ),
            liabilities=BalanceSheetSection(
                classification=AccountClassification.LIABILITY,
                currency=scope.currency,
                lines=(),
            ),
            equity=BalanceSheetSection(
                classification=AccountClassification.EQUITY,
                currency=scope.currency,
                lines=(),
            ),
            current_period_result=CurrentPeriodResult(
                currency=scope.currency,
                revenue_total=zero,
                expense_total=zero,
            ),
        ),
        income_statement=IncomeStatement(
            scope=scope,
            revenues=IncomeStatementSection(
                classification=AccountClassification.REVENUE,
                currency=scope.currency,
                lines=(),
            ),
            expenses=IncomeStatementSection(
                classification=AccountClassification.EXPENSE,
                currency=scope.currency,
                lines=(),
            ),
        ),
    )


def _source() -> YearEndSnapshotSource:
    scope = _scope()
    return YearEndSnapshotSource(
        trial_balance=TrialBalance(scope=scope, lines=()),
        financial_statements=_financial_statements(scope),
        source_version=4,
    )


def _command() -> CreateYearEndSnapshotCommand:
    return CreateYearEndSnapshotCommand(
        snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        idempotency_key=IdempotencyKey(value="year-end-snapshot-2026"),
    )


def _use_case(
    *,
    source: YearEndSnapshotSource | None = None,
    repository: _FakeSnapshotRepository | None = None,
    prerequisites: _FakePrerequisiteRepository | None = None,
    idempotency_repository: _FakeIdempotencyRepository | None = None,
    uow: _FakeUnitOfWork | None = None,
) -> tuple[CreateYearEndSnapshot, _FakeSourceRepository, _FakeSnapshotRepository]:
    source_repository = _FakeSourceRepository(source=_source() if source is None else source)
    snapshot_repository = repository or _FakeSnapshotRepository(
        snapshots={},
        scoped_snapshots={},
        add_calls=[],
    )
    return (
        CreateYearEndSnapshot(
            source_repository=source_repository,
            snapshot_repository=snapshot_repository,
            prerequisites=prerequisites or _FakePrerequisiteRepository(),
            idempotency_repository=idempotency_repository
            or _FakeIdempotencyRepository(values={}),
            uow=uow or _FakeUnitOfWork(),
            clock=_FixedClock(),
        ),
        source_repository,
        snapshot_repository,
    )


def test_create_year_end_snapshot_returns_and_persists_canonical_result() -> None:
    idempotency_repository = _FakeIdempotencyRepository(values={})
    uow = _FakeUnitOfWork()
    use_case, source_repository, snapshot_repository = _use_case(
        idempotency_repository=idempotency_repository,
        uow=uow,
    )

    result = use_case.execute(_command())

    assert result == CreateYearEndSnapshotResult(
        snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        source_version=4,
        captured_at=datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
        idempotent_replay=False,
    )
    assert source_repository.calls == 1
    assert len(snapshot_repository.add_calls) == 1
    assert snapshot_repository.add_calls[0][1] == 4
    assert idempotency_repository.get(_command().idempotency_key) == result
    assert uow.entered == 1


def test_create_year_end_snapshot_replay_skips_source_and_persistence() -> None:
    canonical = CreateYearEndSnapshotResult(
        snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        source_version=4,
        captured_at=datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
        idempotent_replay=False,
    )
    use_case, source_repository, snapshot_repository = _use_case(
        idempotency_repository=_FakeIdempotencyRepository(
            values={_command().idempotency_key: canonical},
        ),
    )

    result = use_case.execute(_command())

    assert result == CreateYearEndSnapshotResult(
        snapshot_id=canonical.snapshot_id,
        legal_entity_id=canonical.legal_entity_id,
        fiscal_year=canonical.fiscal_year,
        source_version=canonical.source_version,
        captured_at=canonical.captured_at,
        idempotent_replay=True,
    )
    assert source_repository.calls == 0
    assert snapshot_repository.add_calls == []


def test_create_year_end_snapshot_rejects_existing_scope() -> None:
    existing = YearEndSnapshot.capture(
        id=YearEndSnapshotId(value="YES-EXISTING"),
        trial_balance=_source().trial_balance,
        financial_statements=_source().financial_statements,
        source_version=4,
        captured_at=datetime(2026, 12, 31, 22, 0, tzinfo=UTC),
    )
    repository = _FakeSnapshotRepository(
        snapshots={existing.id: existing},
        scoped_snapshots={(existing.legal_entity_id, existing.fiscal_year): existing},
        add_calls=[],
    )
    use_case, _, _ = _use_case(repository=repository)

    with pytest.raises(YearEndSnapshotAlreadyExistsError):
        use_case.execute(_command())


def test_create_year_end_snapshot_rejects_missing_source() -> None:
    use_case, source_repository, _ = _use_case(source=_source())
    source_repository.source = None

    with pytest.raises(YearEndSnapshotSourceNotFoundError):
        use_case.execute(_command())


def test_create_year_end_snapshot_rejects_closed_fiscal_year() -> None:
    use_case, _, _ = _use_case(
        prerequisites=_FakePrerequisiteRepository(fiscal_year_closed=True),
    )

    with pytest.raises(YearEndSnapshotFiscalYearClosedError):
        use_case.execute(_command())


def test_create_year_end_snapshot_rejects_recorded_entries() -> None:
    use_case, _, _ = _use_case(
        prerequisites=_FakePrerequisiteRepository(recorded_entries=True),
    )

    with pytest.raises(YearEndSnapshotRecordedEntriesExistError):
        use_case.execute(_command())


def test_create_year_end_snapshot_rejects_operation_in_progress() -> None:
    use_case, _, _ = _use_case(
        prerequisites=_FakePrerequisiteRepository(operation_in_progress=True),
    )

    with pytest.raises(YearEndSnapshotOperationInProgressError):
        use_case.execute(_command())


def test_create_year_end_snapshot_rejects_invalid_idempotency_key() -> None:
    use_case, _, _ = _use_case()

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            CreateYearEndSnapshotCommand(
                snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
                legal_entity_id=LegalEntityId(value="entity-01"),
                fiscal_year=FiscalYear(value=2026),
                idempotency_key="year-end-snapshot-2026",  # type: ignore[arg-type]
            ),
        )