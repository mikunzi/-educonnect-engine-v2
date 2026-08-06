"""Executable in-memory accounting full-cycle demonstration.

This module wires existing use cases and domain services end-to-end without
any SQL, ORM, HTTP, or external infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from educonnect_engine.accounting.application.close_accounting_period import (
    CloseAccountingPeriod,
    CloseAccountingPeriodCommand,
)
from educonnect_engine.accounting.application.close_fiscal_year import (
    CloseFiscalYear,
    CloseFiscalYearCommand,
    CloseFiscalYearResult,
)
from educonnect_engine.accounting.application.create_year_end_snapshot import (
    CreateYearEndSnapshot,
    CreateYearEndSnapshotCommand,
)
from educonnect_engine.accounting.application.generate_opening_entries import (
    GenerateOpeningEntries,
    GenerateOpeningEntriesCommand,
)
from educonnect_engine.accounting.application.lock_accounting_period import (
    LockAccountingPeriod,
    LockAccountingPeriodCommand,
)
from educonnect_engine.accounting.application.open_accounting_period import (
    OpenAccountingPeriod,
    OpenAccountingPeriodCommand,
)
from educonnect_engine.accounting.application.post_journal_entry import (
    PostJournalEntry,
    PostJournalEntryCommand,
)
from educonnect_engine.accounting.application.record_journal_entry import (
    RecordJournalEntry,
    RecordJournalEntryCommand,
)
from educonnect_engine.accounting.domain import (
    AccountClassification,
    AccountingPeriod,
    AccountingPeriodId,
    AccountingPeriodStatus,
    AccountNumber,
    BalanceSheet,
    BalanceSheetProjectionService,
    DebitCreditSide,
    FinancialStatementAccountClassifier,
    FinancialStatements,
    FinancialStatementsProjectionService,
    FiscalYearClosing,
    FiscalYearClosingId,
    FiscalYearClosingStatus,
    GenerateOpeningEntriesService,
    IdempotencyKey,
    IncomeStatement,
    IncomeStatementProjectionService,
    JournalEntry,
    JournalEntryId,
    JournalEntryStatus,
    JournalLine,
    Ledger,
    LedgerProjectionService,
    LedgerScope,
    OpeningEntry,
    TrialBalance,
    TrialBalanceProjectionService,
    YearEndSnapshot,
    YearEndSnapshotId,
    YearEndSnapshotSource,
)
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodLifecycleRepository,
    FiscalYearClosingPrerequisiteRepository,
    FiscalYearClosingRepository,
    IdempotencyRepository,
    JournalEntryRepository,
    OpeningEntryRepository,
    UnitOfWork,
    YearEndSnapshotPrerequisiteRepository,
    YearEndSnapshotRepository,
    YearEndSnapshotSourceRepository,
)
from educonnect_engine.shared.clock import Clock
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class FullCycleResult:
    """Computed artifacts for the full accounting cycle."""

    posted_entries: tuple[JournalEntry, ...]
    ledger: Ledger
    trial_balance: TrialBalance
    balance_sheet: BalanceSheet
    income_statement: IncomeStatement
    financial_statements: FinancialStatements
    snapshot: YearEndSnapshot
    closing_result: CloseFiscalYearResult
    opening_entry: OpeningEntry


@dataclass(frozen=True, slots=True)
class _DemoClassifier(FinancialStatementAccountClassifier):
    """Deterministic chart-of-accounts classifier for the demo scenario."""

    def classify(self, account_number: AccountNumber) -> AccountClassification:
        mapping = {
            "1020": AccountClassification.ASSET,
            "1100": AccountClassification.ASSET,
            "1500": AccountClassification.ASSET,
            "2800": AccountClassification.EQUITY,
            "2990": AccountClassification.EQUITY,
            "3400": AccountClassification.REVENUE,
            "6000": AccountClassification.EXPENSE,
        }
        return mapping[account_number.value]


@dataclass
class _InMemoryState:
    """Shared in-memory persistence state across adapters."""

    classifier: FinancialStatementAccountClassifier
    journal_entries: dict[JournalEntryId, JournalEntry]
    periods: dict[AccountingPeriodId, AccountingPeriod]
    closings: dict[FiscalYearClosingId, FiscalYearClosing]
    closed_scopes: set[tuple[LegalEntityId, FiscalYear]]
    snapshots_by_id: dict[YearEndSnapshotId, YearEndSnapshot]
    snapshots_by_scope: dict[tuple[LegalEntityId, FiscalYear], YearEndSnapshot]
    opening_entries_by_snapshot: dict[YearEndSnapshotId, OpeningEntry]
    source_version: int = 1


@dataclass
class _InMemoryJournalEntryRepository(JournalEntryRepository):
    state: _InMemoryState

    def add(self, entry: JournalEntry) -> None:
        self.state.journal_entries[entry.id] = entry

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        return self.state.journal_entries.get(entry_id)

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        current = self.state.journal_entries.get(entry.id)
        if current is None:
            raise ValueError("journal entry not found for posting")
        if current.version != expected_version:
            raise ValueError("journal entry version mismatch")
        if entry.version != expected_version + 1:
            raise ValueError("invalid posted version progression")
        self.state.journal_entries[entry.id] = entry

    def save_reversal(
        self,
        reversal_entry: JournalEntry,
        original_entry_id: JournalEntryId,
        expected_original_version: int,
    ) -> None:
        original = self.state.journal_entries.get(original_entry_id)
        if original is None:
            raise ValueError("original journal entry not found")
        if original.version != expected_original_version:
            raise ValueError("journal entry version mismatch")
        if any(
            entry.correction_of_entry_id == original_entry_id
            for entry in self.state.journal_entries.values()
        ):
            raise ValueError("direct reversal already exists")
        self.state.journal_entries[reversal_entry.id] = reversal_entry


@dataclass
class _InMemoryAccountingPeriodRepository(
    AccountingPeriodLifecycleRepository,
):
    state: _InMemoryState

    def is_open(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        posting_date: date,
    ) -> bool:
        return any(
            period.legal_entity_id == legal_entity_id
            and period.fiscal_year == fiscal_year
            and period.is_open_for(posting_date)
            for period in self.state.periods.values()
        )

    def get_by_id(self, accounting_period_id: AccountingPeriodId) -> AccountingPeriod | None:
        return self.state.periods.get(accounting_period_id)

    def add(self, period: AccountingPeriod) -> None:
        self.state.periods[period.id] = period

    def save(self, period: AccountingPeriod, expected_version: int) -> None:
        current = self.state.periods.get(period.id)
        if current is None:
            raise ValueError("accounting period not found")
        if current.version != expected_version:
            raise ValueError("accounting period version mismatch")
        self.state.periods[period.id] = period

    def has_open_period(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        return any(
            period.legal_entity_id == legal_entity_id
            and period.fiscal_year == fiscal_year
            and period.status is AccountingPeriodStatus.OPEN
            for period in self.state.periods.values()
        )

    def has_overlapping_period(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        start_date: date,
        end_date: date,
    ) -> bool:
        candidate = AccountingPeriod(
            id=AccountingPeriodId(value="candidate-period"),
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year,
            start_date=start_date,
            end_date=end_date,
            status=AccountingPeriodStatus.OPEN,
            version=0,
        )
        return any(
            period.legal_entity_id == legal_entity_id
            and period.fiscal_year == fiscal_year
            and period.overlaps(candidate)
            for period in self.state.periods.values()
        )


@dataclass
class _InMemoryFiscalYearClosingRepository(FiscalYearClosingRepository):
    state: _InMemoryState

    def get_by_id(self, closing_id: FiscalYearClosingId) -> FiscalYearClosing | None:
        return self.state.closings.get(closing_id)

    def exists_closed(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        return (legal_entity_id, fiscal_year) in self.state.closed_scopes

    def save_closed(self, closing: FiscalYearClosing, expected_version: int) -> None:
        if closing.status is not FiscalYearClosingStatus.CLOSED:
            raise ValueError("fiscal year closing must be CLOSED")
        if closing.version != expected_version + 1:
            raise ValueError("invalid fiscal year closing version progression")
        self.state.closings[closing.id] = closing
        self.state.closed_scopes.add((closing.legal_entity_id, closing.fiscal_year))


@dataclass
class _InMemoryYearEndSnapshotSourceRepository(YearEndSnapshotSourceRepository):
    state: _InMemoryState

    def get_consistent_source(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> YearEndSnapshotSource | None:
        scope = LedgerScope(
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year,
            currency=Currency(code="CHF"),
        )
        posted_entries = tuple(
            entry
            for entry in self.state.journal_entries.values()
            if entry.legal_entity_id == legal_entity_id
            and entry.fiscal_year == fiscal_year
            and entry.status is JournalEntryStatus.POSTED
        )
        if not posted_entries:
            return None

        ledger = LedgerProjectionService().project(scope=scope, entries=posted_entries)
        trial_balance = TrialBalanceProjectionService().project(ledger=ledger)
        balance_sheet = BalanceSheetProjectionService().project(
            trial_balance=trial_balance,
            classifier=self.state.classifier,
        )
        income_statement = IncomeStatementProjectionService().project(
            trial_balance=trial_balance,
            classifier=self.state.classifier,
        )
        statements = FinancialStatementsProjectionService().project(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )
        return YearEndSnapshotSource(
            trial_balance=trial_balance,
            financial_statements=statements,
            source_version=self.state.source_version,
        )


@dataclass
class _InMemoryYearEndSnapshotRepository(YearEndSnapshotRepository):
    state: _InMemoryState
    source_repository: YearEndSnapshotSourceRepository

    def get_by_id(self, snapshot_id: YearEndSnapshotId) -> YearEndSnapshot | None:
        return self.state.snapshots_by_id.get(snapshot_id)

    def get_by_scope(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> YearEndSnapshot | None:
        return self.state.snapshots_by_scope.get((legal_entity_id, fiscal_year))

    def add(self, snapshot: YearEndSnapshot, expected_source_version: int) -> None:
        source = self.source_repository.get_consistent_source(
            snapshot.legal_entity_id,
            snapshot.fiscal_year,
        )
        if source is None:
            raise ValueError("snapshot source is missing")
        if source.source_version != expected_source_version:
            raise ValueError("snapshot source version mismatch")
        self.state.snapshots_by_id[snapshot.id] = snapshot
        self.state.snapshots_by_scope[(snapshot.legal_entity_id, snapshot.fiscal_year)] = snapshot


@dataclass
class _InMemoryFiscalYearClosingPrerequisiteRepository(FiscalYearClosingPrerequisiteRepository):
    state: _InMemoryState
    source_repository: YearEndSnapshotSourceRepository

    def are_all_periods_locked(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        scoped = [
            period
            for period in self.state.periods.values()
            if period.legal_entity_id == legal_entity_id and period.fiscal_year == fiscal_year
        ]
        return bool(scoped) and all(
            period.status is AccountingPeriodStatus.LOCKED for period in scoped
        )

    def has_recorded_journal_entries(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        return any(
            entry.legal_entity_id == legal_entity_id
            and entry.fiscal_year == fiscal_year
            and entry.status is JournalEntryStatus.RECORDED
            for entry in self.state.journal_entries.values()
        )

    def has_posting_or_reversal_in_progress(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return False

    def has_coherent_balanced_financial_statements(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        return (
            self.source_repository.get_consistent_source(legal_entity_id, fiscal_year)
            is not None
        )


@dataclass
class _InMemoryYearEndSnapshotPrerequisiteRepository(YearEndSnapshotPrerequisiteRepository):
    state: _InMemoryState
    closing_repository: FiscalYearClosingRepository

    def has_recorded_journal_entries(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        return any(
            entry.legal_entity_id == legal_entity_id
            and entry.fiscal_year == fiscal_year
            and entry.status is JournalEntryStatus.RECORDED
            for entry in self.state.journal_entries.values()
        )

    def has_posting_or_reversal_in_progress(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year)
        return False

    def is_fiscal_year_closed(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> bool:
        return self.closing_repository.exists_closed(legal_entity_id, fiscal_year)


@dataclass
class _InMemoryOpeningEntryRepository(OpeningEntryRepository):
    state: _InMemoryState

    def exists_for_snapshot(self, snapshot_id: YearEndSnapshotId) -> bool:
        return snapshot_id in self.state.opening_entries_by_snapshot

    def add(self, opening_entry: OpeningEntry) -> None:
        self.state.opening_entries_by_snapshot[opening_entry.source_snapshot_id] = opening_entry


@dataclass
class _InMemoryIdempotencyRepository[ResultT](IdempotencyRepository[ResultT]):
    values: dict[IdempotencyKey, ResultT]

    def get(self, key: IdempotencyKey) -> ResultT | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: ResultT) -> None:
        self.values[key] = result


@dataclass
class _InMemoryUnitOfWork(UnitOfWork):
    @contextmanager
    def transaction(self) -> Iterator[None]:
        yield


class _RecordIdGenerator:
    """Deterministic journal-entry id generator."""

    def __init__(self) -> None:
        self._counter = 1

    def __call__(self) -> JournalEntryId:
        value = f"JE-2026-{self._counter:03d}"
        self._counter += 1
        return JournalEntryId(value=value)


def _money(value: str) -> Money:
    return Money(amount=Decimal(value), currency=Currency(code="CHF"))


def _line(account: str, side: DebitCreditSide, amount: str, description: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=_money(amount),
        description=description,
    )


def _record_and_post(
    record_use_case: RecordJournalEntry,
    post_use_case: PostJournalEntry,
    command: RecordJournalEntryCommand,
) -> JournalEntry:
    recorded = record_use_case.execute(command)
    result = post_use_case.execute(
        PostJournalEntryCommand(
            journal_entry_id=recorded.id,
            expected_version=0,
            idempotency_key=IdempotencyKey(value=f"post-{recorded.id.value}"),
        ),
    )
    return post_use_case.repository.get_by_id(result.entry_id)  # type: ignore[return-value]


def run_accounting_full_cycle() -> FullCycleResult:
    """Execute the complete deterministic accounting cycle in memory."""
    legal_entity_id = LegalEntityId(value="acme-ch")
    fiscal_year_2026 = FiscalYear(value=2026)
    fiscal_year_2027 = FiscalYear(value=2027)

    state = _InMemoryState(
        classifier=_DemoClassifier(),
        journal_entries={},
        periods={},
        closings={},
        closed_scopes=set(),
        snapshots_by_id={},
        snapshots_by_scope={},
        opening_entries_by_snapshot={},
        source_version=1,
    )

    uow = _InMemoryUnitOfWork()
    id_generator: Callable[[], JournalEntryId] = _RecordIdGenerator()

    journal_repository = _InMemoryJournalEntryRepository(state=state)
    period_repository = _InMemoryAccountingPeriodRepository(state=state)
    closing_repository = _InMemoryFiscalYearClosingRepository(state=state)
    source_repository = _InMemoryYearEndSnapshotSourceRepository(state=state)
    snapshot_repository = _InMemoryYearEndSnapshotRepository(
        state=state,
        source_repository=source_repository,
    )
    closing_prerequisites = _InMemoryFiscalYearClosingPrerequisiteRepository(
        state=state,
        source_repository=source_repository,
    )
    snapshot_prerequisites = _InMemoryYearEndSnapshotPrerequisiteRepository(
        state=state,
        closing_repository=closing_repository,
    )
    opening_repository = _InMemoryOpeningEntryRepository(state=state)

    open_period = OpenAccountingPeriod(
        repository=period_repository,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
    )
    close_period = CloseAccountingPeriod(
        repository=period_repository,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
    )
    lock_period = LockAccountingPeriod(
        repository=period_repository,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
    )

    record_entry = RecordJournalEntry(repository=journal_repository, id_generator=id_generator)
    post_entry = PostJournalEntry(
        repository=journal_repository,
        period_repository=period_repository,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
        clock=Clock(),
    )

    create_snapshot = CreateYearEndSnapshot(
        source_repository=source_repository,
        snapshot_repository=snapshot_repository,
        prerequisites=snapshot_prerequisites,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
        clock=Clock(),
    )

    close_fiscal_year = CloseFiscalYear(
        repository=closing_repository,
        prerequisites=closing_prerequisites,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
        clock=Clock(),
    )

    generate_opening_entries = GenerateOpeningEntries(
        snapshot_repository=snapshot_repository,
        opening_entry_repository=opening_repository,
        fiscal_year_closing_repository=closing_repository,
        accounting_period_repository=period_repository,
        idempotency_repository=_InMemoryIdempotencyRepository(values={}),
        uow=uow,
        generator=GenerateOpeningEntriesService(),
    )

    open_period.execute(
        OpenAccountingPeriodCommand(
            accounting_period_id=AccountingPeriodId(value="PER-2026"),
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year_2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            idempotency_key=IdempotencyKey(value="open-period-2026"),
        ),
    )
    open_period.execute(
        OpenAccountingPeriodCommand(
            accounting_period_id=AccountingPeriodId(value="PER-2027"),
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year_2027,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 12, 31),
            idempotency_key=IdempotencyKey(value="open-period-2027"),
        ),
    )

    posted_entries = (
        _record_and_post(
            record_entry,
            post_entry,
            RecordJournalEntryCommand(
                legal_entity_id=legal_entity_id,
                fiscal_year=fiscal_year_2026,
                journal_code=JournalCode(value="GEN"),
                reference=JournalReference(value="CAP-2026-001"),
                posting_date=date(2026, 1, 2),
                lines=(
                    _line("1020", DebitCreditSide.DEBIT, "100000.00", "Apport initial"),
                    _line("2800", DebitCreditSide.CREDIT, "100000.00", "Capital social"),
                ),
            ),
        ),
        _record_and_post(
            record_entry,
            post_entry,
            RecordJournalEntryCommand(
                legal_entity_id=legal_entity_id,
                fiscal_year=fiscal_year_2026,
                journal_code=JournalCode(value="GEN"),
                reference=JournalReference(value="INV-2026-001"),
                posting_date=date(2026, 2, 10),
                lines=(
                    _line("1500", DebitCreditSide.DEBIT, "20000.00", "Achat equipement"),
                    _line("1020", DebitCreditSide.CREDIT, "20000.00", "Paiement banque"),
                ),
            ),
        ),
        _record_and_post(
            record_entry,
            post_entry,
            RecordJournalEntryCommand(
                legal_entity_id=legal_entity_id,
                fiscal_year=fiscal_year_2026,
                journal_code=JournalCode(value="VEN"),
                reference=JournalReference(value="FAC-2026-001"),
                posting_date=date(2026, 3, 5),
                lines=(
                    _line("1100", DebitCreditSide.DEBIT, "35000.00", "Facture client"),
                    _line("3400", DebitCreditSide.CREDIT, "35000.00", "Produit de vente"),
                ),
            ),
        ),
        _record_and_post(
            record_entry,
            post_entry,
            RecordJournalEntryCommand(
                legal_entity_id=legal_entity_id,
                fiscal_year=fiscal_year_2026,
                journal_code=JournalCode(value="BAN"),
                reference=JournalReference(value="ENC-2026-001"),
                posting_date=date(2026, 3, 30),
                lines=(
                    _line("1020", DebitCreditSide.DEBIT, "35000.00", "Encaissement client"),
                    _line("1100", DebitCreditSide.CREDIT, "35000.00", "Solde client"),
                ),
            ),
        ),
        _record_and_post(
            record_entry,
            post_entry,
            RecordJournalEntryCommand(
                legal_entity_id=legal_entity_id,
                fiscal_year=fiscal_year_2026,
                journal_code=JournalCode(value="GEN"),
                reference=JournalReference(value="CHG-2026-001"),
                posting_date=date(2026, 4, 15),
                lines=(
                    _line("6000", DebitCreditSide.DEBIT, "5000.00", "Charge exploitation"),
                    _line("1020", DebitCreditSide.CREDIT, "5000.00", "Paiement charge"),
                ),
            ),
        ),
    )

    scope_2026 = LedgerScope(
        legal_entity_id=legal_entity_id,
        fiscal_year=fiscal_year_2026,
        currency=Currency(code="CHF"),
    )
    ledger = LedgerProjectionService().project(scope=scope_2026, entries=posted_entries)
    trial_balance = TrialBalanceProjectionService().project(ledger=ledger)
    balance_sheet = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=state.classifier,
    )
    income_statement = IncomeStatementProjectionService().project(
        trial_balance=trial_balance,
        classifier=state.classifier,
    )
    financial_statements = FinancialStatementsProjectionService().project(
        balance_sheet=balance_sheet,
        income_statement=income_statement,
    )

    snapshot_result = create_snapshot.execute(
        CreateYearEndSnapshotCommand(
            snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year_2026,
            idempotency_key=IdempotencyKey(value="snapshot-2026"),
        ),
    )
    snapshot = state.snapshots_by_id[snapshot_result.snapshot_id]

    close_period.execute(
        CloseAccountingPeriodCommand(
            accounting_period_id=AccountingPeriodId(value="PER-2026"),
            expected_version=0,
            idempotency_key=IdempotencyKey(value="close-period-2026"),
        ),
    )
    lock_period.execute(
        LockAccountingPeriodCommand(
            accounting_period_id=AccountingPeriodId(value="PER-2026"),
            expected_version=1,
            idempotency_key=IdempotencyKey(value="lock-period-2026"),
        ),
    )

    closing_result = close_fiscal_year.execute(
        CloseFiscalYearCommand(
            closing_id=FiscalYearClosingId(value="FYC-2026"),
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year_2026,
            idempotency_key=IdempotencyKey(value="close-fiscal-year-2026"),
        ),
    )

    opening_result = generate_opening_entries.execute(
        GenerateOpeningEntriesCommand(
            source_snapshot_id=snapshot.id,
            journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
            target_fiscal_year=fiscal_year_2027,
            journal_code=JournalCode(value="OPEN"),
            reference=JournalReference(value="OPEN-2027-001"),
            posting_date=date(2027, 1, 1),
            retained_earnings_account_number=AccountNumber(value="2990"),
            idempotency_key=IdempotencyKey(value="opening-entries-2027"),
        ),
    )
    opening_entry = state.opening_entries_by_snapshot[opening_result.source_snapshot_id]

    return FullCycleResult(
        posted_entries=posted_entries,
        ledger=ledger,
        trial_balance=trial_balance,
        balance_sheet=balance_sheet,
        income_statement=income_statement,
        financial_statements=financial_statements,
        snapshot=snapshot,
        closing_result=closing_result,
        opening_entry=opening_entry,
    )


def main() -> None:
    """Run the demonstration and print a concise summary."""
    result = run_accounting_full_cycle()
    print(f"Posted entries: {len(result.posted_entries)}")
    print(
        "Trial balance totals:",
        f"debit={result.trial_balance.total_debit().amount}",
        f"credit={result.trial_balance.total_credit().amount}",
    )
    print(
        "Net result:",
        result.income_statement.net_result_side().value,
        result.income_statement.net_result_amount().amount,
    )
    print("Snapshot:", result.snapshot.id.value, "FY", result.snapshot.fiscal_year.value)
    print("Opening entry lines:", len(result.opening_entry.journal_entry.lines))


if __name__ == "__main__":
    main()
