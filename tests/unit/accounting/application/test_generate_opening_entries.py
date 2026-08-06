"""Unit tests for GenerateOpeningEntries use case."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from educonnect_engine.accounting.application.generate_opening_entries import (
    GenerateOpeningEntries,
    GenerateOpeningEntriesAlreadyExistsError,
    GenerateOpeningEntriesCommand,
    GenerateOpeningEntriesResult,
    InvalidIdempotencyKeyError,
    OpeningEntriesSourceFiscalYearNotClosedError,
    OpeningEntriesTargetPeriodNotOpenError,
    YearEndSnapshotNotFoundError,
)
from educonnect_engine.accounting.domain.generate_opening_entries_service import (
    GenerateOpeningEntriesService,
)
from educonnect_engine.accounting.domain.opening_entry import OpeningEntry
from educonnect_engine.accounting.domain.opening_entry_status import OpeningEntryStatus

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_section import BalanceSheetSection
from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.financial_statements import FinancialStatements
from educonnect_engine.accounting.domain.fiscal_year_closing import FiscalYearClosing
from educonnect_engine.accounting.domain.fiscal_year_closing_id import FiscalYearClosingId
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_section import IncomeStatementSection
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodRepository,
    FiscalYearClosingRepository,
    IdempotencyRepository,
    OpeningEntryRepository,
    UnitOfWork,
    YearEndSnapshotRepository,
)
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.year_end_snapshot import YearEndSnapshot
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _FakeSnapshotRepository(YearEndSnapshotRepository):
    snapshot: YearEndSnapshot | None

    def get_by_id(self, snapshot_id: YearEndSnapshotId) -> YearEndSnapshot | None:
        _ = snapshot_id
        return self.snapshot

    def get_by_scope(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> YearEndSnapshot | None:
        _ = (legal_entity_id, fiscal_year)
        return self.snapshot

    def add(self, snapshot: YearEndSnapshot, expected_source_version: int) -> None:
        _ = (snapshot, expected_source_version)


@dataclass
class _FakeOpeningEntryRepository(OpeningEntryRepository):
    exists: bool = False
    added: list[OpeningEntry] | None = None

    def exists_for_snapshot(self, snapshot_id: YearEndSnapshotId) -> bool:
        _ = snapshot_id
        return self.exists

    def add(self, opening_entry: OpeningEntry) -> None:
        if self.added is not None:
            self.added.append(opening_entry)


@dataclass
class _FakeFiscalYearClosingRepository(FiscalYearClosingRepository):
    closed: bool = True

    def get_by_id(self, closing_id: FiscalYearClosingId) -> FiscalYearClosing | None:
        _ = closing_id
        return None

    def exists_closed(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return self.closed

    def save_closed(self, closing: FiscalYearClosing, expected_version: int) -> None:
        _ = (closing, expected_version)


@dataclass
class _FakeAccountingPeriodRepository(AccountingPeriodRepository):
    open_flag: bool = True

    def is_open(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        posting_date: date,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year, posting_date)
        return self.open_flag


@dataclass
class _FakeIdempotencyRepository(IdempotencyRepository[GenerateOpeningEntriesResult]):
    values: dict[IdempotencyKey, GenerateOpeningEntriesResult]

    def get(self, key: IdempotencyKey) -> GenerateOpeningEntriesResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: GenerateOpeningEntriesResult) -> None:
        self.values[key] = result


@dataclass
class _FakeUnitOfWork(UnitOfWork):
    entered: int = 0

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self.entered += 1
        yield


class _FakeGenerator(GenerateOpeningEntriesService):
    calls: int = 0

    @classmethod
    def generate(
        cls,
        *,
        snapshot: YearEndSnapshot,
        journal_entry_id: JournalEntryId,
        target_fiscal_year: FiscalYear,
        journal_code: JournalCode,
        reference: JournalReference,
        posting_date: date,
        retained_earnings_account_number: AccountNumber,
    ) -> OpeningEntry:
        cls.calls += 1
        _ = (
            snapshot,
            journal_entry_id,
            target_fiscal_year,
            journal_code,
            reference,
            posting_date,
            retained_earnings_account_number,
        )
        return _opening_entry()


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _snapshot() -> YearEndSnapshot:
    scope = _scope()
    zero = Money(amount=Decimal("0"), currency=scope.currency)
    statements = FinancialStatements(
        balance_sheet=BalanceSheet(
            scope=scope,
            assets=BalanceSheetSection(AccountClassification.ASSET, scope.currency, ()),
            liabilities=BalanceSheetSection(AccountClassification.LIABILITY, scope.currency, ()),
            equity=BalanceSheetSection(AccountClassification.EQUITY, scope.currency, ()),
            current_period_result=CurrentPeriodResult(scope.currency, zero, zero),
        ),
        income_statement=IncomeStatement(
            scope=scope,
            revenues=IncomeStatementSection(AccountClassification.REVENUE, scope.currency, ()),
            expenses=IncomeStatementSection(AccountClassification.EXPENSE, scope.currency, ()),
        ),
    )
    return YearEndSnapshot.capture(
        id=YearEndSnapshotId(value="YES-2026-001"),
        trial_balance=TrialBalance(scope=scope, lines=()),
        financial_statements=statements,
        source_version=4,
        captured_at=datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
    )


def _opening_entry() -> OpeningEntry:
    journal_entry = JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-OPEN-2027"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2027),
        journal_code=JournalCode(value="OPEN"),
        reference=JournalReference(value="OPEN-2027"),
        posting_date=date(2027, 1, 1),
        lines=(
            JournalLine(
                AccountNumber(value="1000"),
                DebitCreditSide.DEBIT,
                Money(Decimal("100.00"), Currency(code="CHF")),
                "Opening balance",
            ),
            JournalLine(
                AccountNumber(value="2000"),
                DebitCreditSide.CREDIT,
                Money(Decimal("100.00"), Currency(code="CHF")),
                "Opening balance",
            ),
        ),
    )
    return OpeningEntry.generate(
        source_snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        source_legal_entity_id=LegalEntityId(value="entity-01"),
        source_fiscal_year=FiscalYear(value=2026),
        journal_entry=journal_entry,
    )


def _command() -> GenerateOpeningEntriesCommand:
    return GenerateOpeningEntriesCommand(
        source_snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
        target_fiscal_year=FiscalYear(value=2027),
        journal_code=JournalCode(value="OPEN"),
        reference=JournalReference(value="OPEN-2027"),
        posting_date=date(2027, 1, 1),
        retained_earnings_account_number=AccountNumber(value="2990"),
        idempotency_key=IdempotencyKey(value="generate-opening-2027"),
    )


def _use_case(
    *,
    snapshot_available: bool = True,
    opening_repository: _FakeOpeningEntryRepository | None = None,
    closing_repository: _FakeFiscalYearClosingRepository | None = None,
    period_repository: _FakeAccountingPeriodRepository | None = None,
    idempotency_repository: _FakeIdempotencyRepository | None = None,
    uow: _FakeUnitOfWork | None = None,
) -> GenerateOpeningEntries:
    _FakeGenerator.calls = 0
    return GenerateOpeningEntries(
        snapshot_repository=_FakeSnapshotRepository(
            _snapshot() if snapshot_available else None,
        ),
        opening_entry_repository=opening_repository or _FakeOpeningEntryRepository(added=[]),
        fiscal_year_closing_repository=closing_repository
        or _FakeFiscalYearClosingRepository(),
        accounting_period_repository=period_repository or _FakeAccountingPeriodRepository(),
        idempotency_repository=idempotency_repository or _FakeIdempotencyRepository(values={}),
        uow=uow or _FakeUnitOfWork(),
        generator=_FakeGenerator(),
    )


def test_generate_opening_entries_persists_canonical_generated_entry() -> None:
    repository = _FakeOpeningEntryRepository(added=[])
    idempotency_repository = _FakeIdempotencyRepository(values={})
    uow = _FakeUnitOfWork()
    use_case = _use_case(
        opening_repository=repository,
        idempotency_repository=idempotency_repository,
        uow=uow,
    )

    result = use_case.execute(_command())

    assert result == GenerateOpeningEntriesResult(
        source_snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
        target_fiscal_year=FiscalYear(value=2027),
        status=OpeningEntryStatus.GENERATED,
        idempotent_replay=False,
    )
    assert repository.added == [_opening_entry()]
    assert _FakeGenerator.calls == 1
    assert idempotency_repository.get(_command().idempotency_key) == result
    assert uow.entered == 1


def test_generate_opening_entries_replay_skips_generation_and_persistence() -> None:
    canonical = GenerateOpeningEntriesResult(
        source_snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
        target_fiscal_year=FiscalYear(value=2027),
        status=OpeningEntryStatus.GENERATED,
        idempotent_replay=False,
    )
    repository = _FakeOpeningEntryRepository(added=[])
    use_case = _use_case(
        opening_repository=repository,
        idempotency_repository=_FakeIdempotencyRepository(
            values={_command().idempotency_key: canonical},
        ),
    )

    result = use_case.execute(_command())

    assert result.idempotent_replay is True
    assert repository.added == []
    assert _FakeGenerator.calls == 0


def test_generate_opening_entries_rejects_missing_snapshot() -> None:
    use_case = _use_case(snapshot_available=False)

    with pytest.raises(YearEndSnapshotNotFoundError):
        use_case.execute(_command())


def test_generate_opening_entries_rejects_existing_generation() -> None:
    use_case = _use_case(opening_repository=_FakeOpeningEntryRepository(exists=True))

    with pytest.raises(GenerateOpeningEntriesAlreadyExistsError):
        use_case.execute(_command())


def test_generate_opening_entries_requires_closed_source_fiscal_year() -> None:
    use_case = _use_case(
        closing_repository=_FakeFiscalYearClosingRepository(closed=False),
    )

    with pytest.raises(OpeningEntriesSourceFiscalYearNotClosedError):
        use_case.execute(_command())


def test_generate_opening_entries_requires_open_target_period() -> None:
    use_case = _use_case(
        period_repository=_FakeAccountingPeriodRepository(open_flag=False),
    )

    with pytest.raises(OpeningEntriesTargetPeriodNotOpenError):
        use_case.execute(_command())


def test_generate_opening_entries_rejects_invalid_idempotency_key() -> None:
    use_case = _use_case()

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            GenerateOpeningEntriesCommand(
                source_snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
                journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
                target_fiscal_year=FiscalYear(value=2027),
                journal_code=JournalCode(value="OPEN"),
                reference=JournalReference(value="OPEN-2027"),
                posting_date=date(2027, 1, 1),
                retained_earnings_account_number=AccountNumber(value="2990"),
                idempotency_key=cast(IdempotencyKey, "generate-opening-2027"),
            ),
        )
