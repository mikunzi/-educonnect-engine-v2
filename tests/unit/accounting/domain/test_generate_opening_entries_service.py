"""Unit tests for GenerateOpeningEntriesService."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from educonnect_engine.accounting.domain.generate_opening_entries_service import (
    EmptyOpeningEntryError,
    GenerateOpeningEntriesService,
    OpeningEntryRetainedEarningsAccountConflictError,
    OpeningEntryTargetFiscalYearError,
)
from educonnect_engine.accounting.domain.opening_entry import OpeningEntry
from educonnect_engine.accounting.domain.opening_entry_status import OpeningEntryStatus

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_line import BalanceSheetLine
from educonnect_engine.accounting.domain.balance_sheet_section import BalanceSheetSection
from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.financial_statements import FinancialStatements
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_line import IncomeStatementLine
from educonnect_engine.accounting.domain.income_statement_section import IncomeStatementSection
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.trial_balance_line import TrialBalanceLine
from educonnect_engine.accounting.domain.year_end_snapshot import YearEndSnapshot
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code="CHF"))


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _tb_line(account: str, debit: str, credit: str) -> TrialBalanceLine:
    return TrialBalanceLine(
        account_number=AccountNumber(value=account),
        currency=Currency(code="CHF"),
        debit_movement=_money(debit),
        credit_movement=_money(credit),
    )


def _bs_line(
    account: str,
    classification: AccountClassification,
    side: DebitCreditSide,
    amount: str,
) -> BalanceSheetLine:
    return BalanceSheetLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code="CHF"),
        balance_side=side,
        balance_amount=_money(amount),
    )


def _is_line(
    account: str,
    classification: AccountClassification,
    side: DebitCreditSide,
    amount: str,
) -> IncomeStatementLine:
    return IncomeStatementLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code="CHF"),
        balance_side=side,
        balance_amount=_money(amount),
    )


def _snapshot(*, loss: bool = False, empty: bool = False) -> YearEndSnapshot:
    scope = _scope()
    if empty:
        trial_balance_lines: tuple[TrialBalanceLine, ...] = ()
        asset_lines: tuple[BalanceSheetLine, ...] = ()
        liability_lines: tuple[BalanceSheetLine, ...] = ()
        equity_lines: tuple[BalanceSheetLine, ...] = ()
        revenue_lines: tuple[IncomeStatementLine, ...] = ()
        expense_lines: tuple[IncomeStatementLine, ...] = ()
        revenue_total = "0"
        expense_total = "0"
    elif loss:
        trial_balance_lines = (
            _tb_line("1000", "95.00", "0"),
            _tb_line("2000", "0", "40.00"),
            _tb_line("3000", "0", "60.00"),
            _tb_line("4000", "0", "15.00"),
            _tb_line("5000", "20.00", "0"),
        )
        asset_lines = (
            _bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "95.00"),
        )
        liability_lines = (
            _bs_line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "40.00"),
        )
        equity_lines = (
            _bs_line("3000", AccountClassification.EQUITY, DebitCreditSide.CREDIT, "60.00"),
        )
        revenue_lines = (
            _is_line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "15.00"),
        )
        expense_lines = (
            _is_line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "20.00"),
        )
        revenue_total = "15.00"
        expense_total = "20.00"
    else:
        trial_balance_lines = (
            _tb_line("1000", "100.00", "0"),
            _tb_line("2000", "0", "70.00"),
            _tb_line("4000", "0", "50.00"),
            _tb_line("5000", "20.00", "0"),
        )
        asset_lines = (
            _bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),
        )
        liability_lines = (
            _bs_line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "70.00"),
        )
        equity_lines = ()
        revenue_lines = (
            _is_line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "50.00"),
        )
        expense_lines = (
            _is_line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "20.00"),
        )
        revenue_total = "50.00"
        expense_total = "20.00"

    statements = FinancialStatements(
        balance_sheet=BalanceSheet(
            scope=scope,
            assets=BalanceSheetSection(
                classification=AccountClassification.ASSET,
                currency=scope.currency,
                lines=asset_lines,
            ),
            liabilities=BalanceSheetSection(
                classification=AccountClassification.LIABILITY,
                currency=scope.currency,
                lines=liability_lines,
            ),
            equity=BalanceSheetSection(
                classification=AccountClassification.EQUITY,
                currency=scope.currency,
                lines=equity_lines,
            ),
            current_period_result=CurrentPeriodResult(
                currency=scope.currency,
                revenue_total=_money(revenue_total),
                expense_total=_money(expense_total),
            ),
        ),
        income_statement=IncomeStatement(
            scope=scope,
            revenues=IncomeStatementSection(
                classification=AccountClassification.REVENUE,
                currency=scope.currency,
                lines=revenue_lines,
            ),
            expenses=IncomeStatementSection(
                classification=AccountClassification.EXPENSE,
                currency=scope.currency,
                lines=expense_lines,
            ),
        ),
    )
    return YearEndSnapshot.capture(
        id=YearEndSnapshotId(value="YES-2026-001"),
        trial_balance=TrialBalance(scope=scope, lines=trial_balance_lines),
        financial_statements=statements,
        source_version=4,
        captured_at=datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
    )


def _generate(snapshot: YearEndSnapshot | None = None) -> OpeningEntry:
    return GenerateOpeningEntriesService.generate(
        snapshot=snapshot or _snapshot(),
        journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
        target_fiscal_year=FiscalYear(value=2027),
        journal_code=JournalCode(value="OPEN"),
        reference=JournalReference(value="OPEN-2027"),
        posting_date=date(2027, 1, 1),
        retained_earnings_account_number=AccountNumber(value="2990"),
    )


def test_generate_opening_entry_carries_balance_sheet_balances_and_profit() -> None:
    opening_entry = _generate()

    assert opening_entry.status is OpeningEntryStatus.GENERATED
    assert opening_entry.source_snapshot_id == YearEndSnapshotId(value="YES-2026-001")
    actual_lines = [
        (line.account_number.value, line.side, line.amount.amount)
        for line in opening_entry.journal_entry.lines
    ]
    assert actual_lines == [
        ("1000", DebitCreditSide.DEBIT, Decimal("100.00")),
        ("2000", DebitCreditSide.CREDIT, Decimal("70.00")),
        ("2990", DebitCreditSide.CREDIT, Decimal("30.00")),
    ]
    assert opening_entry.journal_entry.total_debit() == _money("100.00")
    assert opening_entry.journal_entry.total_credit() == _money("100.00")


def test_generate_opening_entry_carries_loss_on_debit_side() -> None:
    opening_entry = _generate(_snapshot(loss=True))

    actual_lines = [
        (line.account_number.value, line.side, line.amount.amount)
        for line in opening_entry.journal_entry.lines
    ]
    assert actual_lines == [
        ("1000", DebitCreditSide.DEBIT, Decimal("95.00")),
        ("2000", DebitCreditSide.CREDIT, Decimal("40.00")),
        ("2990", DebitCreditSide.DEBIT, Decimal("5.00")),
        ("3000", DebitCreditSide.CREDIT, Decimal("60.00")),
    ]


def test_generate_opening_entry_excludes_revenue_and_expense_accounts() -> None:
    opening_entry = _generate()
    accounts = {line.account_number.value for line in opening_entry.journal_entry.lines}

    assert "4000" not in accounts
    assert "5000" not in accounts


def test_generate_opening_entry_is_deterministic() -> None:
    first = _generate()
    second = _generate()

    assert first == second


def test_generate_opening_entry_rejects_non_consecutive_target_year() -> None:
    with pytest.raises(OpeningEntryTargetFiscalYearError):
        GenerateOpeningEntriesService.generate(
            snapshot=_snapshot(),
            journal_entry_id=JournalEntryId(value="JE-OPEN-2028"),
            target_fiscal_year=FiscalYear(value=2028),
            journal_code=JournalCode(value="OPEN"),
            reference=JournalReference(value="OPEN-2028"),
            posting_date=date(2028, 1, 1),
            retained_earnings_account_number=AccountNumber(value="2990"),
        )


def test_generate_opening_entry_rejects_retained_earnings_account_collision() -> None:
    with pytest.raises(OpeningEntryRetainedEarningsAccountConflictError):
        GenerateOpeningEntriesService.generate(
            snapshot=_snapshot(),
            journal_entry_id=JournalEntryId(value="JE-OPEN-2027"),
            target_fiscal_year=FiscalYear(value=2027),
            journal_code=JournalCode(value="OPEN"),
            reference=JournalReference(value="OPEN-2027"),
            posting_date=date(2027, 1, 1),
            retained_earnings_account_number=AccountNumber(value="2000"),
        )


def test_generate_opening_entry_rejects_empty_exercise() -> None:
    with pytest.raises(EmptyOpeningEntryError):
        _generate(_snapshot(empty=True))
