"""Unit tests for BalanceSheet."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet import (
    BalanceSheet,
    UnbalancedBalanceSheetError,
)
from educonnect_engine.accounting.domain.balance_sheet_line import BalanceSheetLine
from educonnect_engine.accounting.domain.balance_sheet_section import BalanceSheetSection
from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code="CHF"))


def _line(
    account: str,
    classification: AccountClassification,
    side: DebitCreditSide | None,
    amount: str,
) -> BalanceSheetLine:
    return BalanceSheetLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code="CHF"),
        balance_side=side,
        balance_amount=_money(amount),
    )


def _section(
    classification: AccountClassification,
    lines: tuple[BalanceSheetLine, ...],
) -> BalanceSheetSection:
    return BalanceSheetSection(
        classification=classification,
        currency=Currency(code="CHF"),
        lines=lines,
    )


def test_balance_sheet_empty_is_valid() -> None:
    empty_result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )
    balance_sheet = BalanceSheet(
        scope=_scope(),
        assets=_section(AccountClassification.ASSET, ()),
        liabilities=_section(AccountClassification.LIABILITY, ()),
        equity=_section(AccountClassification.EQUITY, ()),
        current_period_result=empty_result,
    )

    assert balance_sheet.assets_total() == _money("0")
    assert balance_sheet.right_side_total() == _money("0")
    assert balance_sheet.is_balanced() is True


def test_balance_sheet_before_closing_is_balanced_with_result() -> None:
    before_result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("50.00"),
        expense_total=_money("20.00"),
    )
    balance_sheet = BalanceSheet(
        scope=_scope(),
        assets=_section(
            AccountClassification.ASSET,
            (_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),),
        ),
        liabilities=_section(
            AccountClassification.LIABILITY,
            (_line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "70.00"),),
        ),
        equity=_section(AccountClassification.EQUITY, ()),
        current_period_result=before_result,
    )

    assert balance_sheet.is_balanced() is True
    assert balance_sheet.right_side_total() == _money("100.00")


def test_balance_sheet_after_closing_is_balanced_without_result() -> None:
    after_result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )
    balance_sheet = BalanceSheet(
        scope=_scope(),
        assets=_section(
            AccountClassification.ASSET,
            (_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),),
        ),
        liabilities=_section(
            AccountClassification.LIABILITY,
            (_line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "70.00"),),
        ),
        equity=_section(
            AccountClassification.EQUITY,
            (_line("3000", AccountClassification.EQUITY, DebitCreditSide.CREDIT, "30.00"),),
        ),
        current_period_result=after_result,
    )

    assert balance_sheet.is_balanced() is True
    assert balance_sheet.right_side_total() == _money("100.00")


def test_balance_sheet_rejects_unbalanced_totals() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )

    with pytest.raises(UnbalancedBalanceSheetError):
        BalanceSheet(
            scope=_scope(),
            assets=_section(
                AccountClassification.ASSET,
                (_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),),
            ),
            liabilities=_section(
                AccountClassification.LIABILITY,
                (_line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "70.00"),),
            ),
            equity=_section(AccountClassification.EQUITY, ()),
            current_period_result=result,
        )


def test_balance_sheet_rejects_invalid_assets_section_classification() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )

    with pytest.raises(ValueError, match="assets section"):
        BalanceSheet(
            scope=_scope(),
            assets=_section(AccountClassification.EQUITY, ()),
            liabilities=_section(AccountClassification.LIABILITY, ()),
            equity=_section(AccountClassification.EQUITY, ()),
            current_period_result=result,
        )


def test_balance_sheet_rejects_invalid_liabilities_section_classification() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )

    with pytest.raises(ValueError, match="liabilities section"):
        BalanceSheet(
            scope=_scope(),
            assets=_section(AccountClassification.ASSET, ()),
            liabilities=_section(AccountClassification.EQUITY, ()),
            equity=_section(AccountClassification.EQUITY, ()),
            current_period_result=result,
        )


def test_balance_sheet_rejects_invalid_equity_section_classification() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )

    with pytest.raises(ValueError, match="equity section"):
        BalanceSheet(
            scope=_scope(),
            assets=_section(AccountClassification.ASSET, ()),
            liabilities=_section(AccountClassification.LIABILITY, ()),
            equity=_section(AccountClassification.LIABILITY, ()),
            current_period_result=result,
        )


def test_balance_sheet_rejects_section_currency_mismatch() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("0"),
        expense_total=_money("0"),
    )
    euro_asset = BalanceSheetSection(
        classification=AccountClassification.ASSET,
        currency=Currency(code="EUR"),
        lines=(),
    )

    with pytest.raises(ValueError, match="section currency"):
        BalanceSheet(
            scope=_scope(),
            assets=euro_asset,
            liabilities=_section(AccountClassification.LIABILITY, ()),
            equity=_section(AccountClassification.EQUITY, ()),
            current_period_result=result,
        )


def test_balance_sheet_rejects_current_period_result_currency_mismatch() -> None:
    mismatch_result = CurrentPeriodResult(
        currency=Currency(code="EUR"),
        revenue_total=Money(amount=Decimal("0"), currency=Currency(code="EUR")),
        expense_total=Money(amount=Decimal("0"), currency=Currency(code="EUR")),
    )

    with pytest.raises(ValueError, match="current period result currency"):
        BalanceSheet(
            scope=_scope(),
            assets=_section(AccountClassification.ASSET, ()),
            liabilities=_section(AccountClassification.LIABILITY, ()),
            equity=_section(AccountClassification.EQUITY, ()),
            current_period_result=mismatch_result,
        )


def test_balance_sheet_totals_and_loss_branch_are_exposed() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("20.00"),
        expense_total=_money("30.00"),
    )
    balance_sheet = BalanceSheet(
        scope=_scope(),
        assets=_section(
            AccountClassification.ASSET,
            (_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "90.00"),),
        ),
        liabilities=_section(
            AccountClassification.LIABILITY,
            (_line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "40.00"),),
        ),
        equity=_section(
            AccountClassification.EQUITY,
            (_line("3000", AccountClassification.EQUITY, DebitCreditSide.CREDIT, "60.00"),),
        ),
        current_period_result=result,
    )

    assert balance_sheet.liabilities_total() == _money("40.00")
    assert balance_sheet.equity_total() == _money("60.00")
    assert balance_sheet.right_side_total() == _money("90.00")
    assert balance_sheet.is_balanced() is True
