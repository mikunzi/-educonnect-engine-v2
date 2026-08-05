"""Unit tests for YearEndSnapshot."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_section import BalanceSheetSection
from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.financial_statements import FinancialStatements
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_section import IncomeStatementSection
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.year_end_snapshot import (
    YearEndSnapshot,
    YearEndSnapshotCurrencyMismatchError,
    YearEndSnapshotScopeMismatchError,
    YearEndSnapshotSourceVersionError,
    YearEndSnapshotTimestampError,
)
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _scope(
    *,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2026,
    currency: str = "CHF",
) -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value=legal_entity_id),
        fiscal_year=FiscalYear(value=fiscal_year),
        currency=Currency(code=currency),
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


def _capture(
    *,
    trial_balance_scope: LedgerScope | None = None,
    statements_scope: LedgerScope | None = None,
    source_version: int = 4,
    captured_at: datetime = datetime(2026, 12, 31, 23, 0, tzinfo=UTC),
) -> YearEndSnapshot:
    trial_balance_scope = trial_balance_scope or _scope()
    statements_scope = statements_scope or trial_balance_scope
    return YearEndSnapshot.capture(
        id=YearEndSnapshotId(value="YES-2026-001"),
        trial_balance=TrialBalance(scope=trial_balance_scope, lines=()),
        financial_statements=_financial_statements(statements_scope),
        source_version=source_version,
        captured_at=captured_at,
    )


def test_year_end_snapshot_captures_coherent_source() -> None:
    snapshot = _capture()

    assert snapshot.id == YearEndSnapshotId(value="YES-2026-001")
    assert snapshot.trial_balance == TrialBalance(scope=_scope(), lines=())
    assert snapshot.financial_statements == _financial_statements(_scope())
    assert snapshot.source_version == 4
    assert snapshot.captured_at == datetime(2026, 12, 31, 23, 0, tzinfo=UTC)
    assert snapshot.legal_entity_id == LegalEntityId(value="entity-01")
    assert snapshot.fiscal_year == FiscalYear(value=2026)
    assert snapshot.currency == Currency(code="CHF")


def test_year_end_snapshot_is_frozen_and_slotted() -> None:
    snapshot = _capture()

    with pytest.raises(FrozenInstanceError):
        type(snapshot).__setattr__(snapshot, "source_version", 5)

    assert not hasattr(snapshot, "__dict__")


@pytest.mark.parametrize(
    "statements_scope",
    [
        _scope(legal_entity_id="entity-02"),
        _scope(fiscal_year=2027),
    ],
)
def test_year_end_snapshot_rejects_scope_mismatch(
    statements_scope: LedgerScope,
) -> None:
    with pytest.raises(YearEndSnapshotScopeMismatchError):
        _capture(statements_scope=statements_scope)


def test_year_end_snapshot_rejects_currency_mismatch() -> None:
    with pytest.raises(YearEndSnapshotCurrencyMismatchError):
        _capture(statements_scope=_scope(currency="EUR"))


def test_year_end_snapshot_rejects_negative_source_version() -> None:
    with pytest.raises(YearEndSnapshotSourceVersionError):
        _capture(source_version=-1)


def test_year_end_snapshot_rejects_naive_timestamp() -> None:
    with pytest.raises(YearEndSnapshotTimestampError):
        _capture(captured_at=datetime(2026, 12, 31, 23, 0))


def test_year_end_snapshot_rejects_non_utc_timestamp() -> None:
    utc_plus_one = timezone(timedelta(hours=1))

    with pytest.raises(YearEndSnapshotTimestampError):
        _capture(captured_at=datetime(2027, 1, 1, 0, 0, tzinfo=utc_plus_one))