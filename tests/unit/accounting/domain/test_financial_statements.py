"""Unit tests for FinancialStatements."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_line import BalanceSheetLine
from educonnect_engine.accounting.domain.balance_sheet_section import BalanceSheetSection
from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.financial_statements import (
    FinancialStatements,
    FinancialStatementsCurrencyMismatchError,
    FinancialStatementsNetResultMismatchError,
    FinancialStatementsScopeMismatchError,
)
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_line import IncomeStatementLine
from educonnect_engine.accounting.domain.income_statement_section import IncomeStatementSection
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


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


def _bs_line(
    account: str,
    classification: AccountClassification,
    side: DebitCreditSide | None,
    amount: str,
    currency: str = "CHF",
) -> BalanceSheetLine:
    return BalanceSheetLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code=currency),
        balance_side=side,
        balance_amount=_money(amount, currency),
    )


def _bs_section(
    classification: AccountClassification,
    lines: tuple[BalanceSheetLine, ...],
    currency: str = "CHF",
) -> BalanceSheetSection:
    return BalanceSheetSection(
        classification=classification,
        currency=Currency(code=currency),
        lines=lines,
    )


def _balance_sheet(
    *,
    scope: LedgerScope,
    current_period_result: CurrentPeriodResult,
    assets_lines: tuple[BalanceSheetLine, ...],
    liabilities_lines: tuple[BalanceSheetLine, ...],
    equity_lines: tuple[BalanceSheetLine, ...],
) -> BalanceSheet:
    return BalanceSheet(
        scope=scope,
        assets=_bs_section(AccountClassification.ASSET, assets_lines, scope.currency.code),
        liabilities=_bs_section(
            AccountClassification.LIABILITY,
            liabilities_lines,
            scope.currency.code,
        ),
        equity=_bs_section(AccountClassification.EQUITY, equity_lines, scope.currency.code),
        current_period_result=current_period_result,
    )


def _is_line(
    account: str,
    classification: AccountClassification,
    side: DebitCreditSide | None,
    amount: str,
    currency: str = "CHF",
) -> IncomeStatementLine:
    return IncomeStatementLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code=currency),
        balance_side=side,
        balance_amount=_money(amount, currency),
    )


def _is_section(
    classification: AccountClassification,
    lines: tuple[IncomeStatementLine, ...],
    currency: str = "CHF",
) -> IncomeStatementSection:
    return IncomeStatementSection(
        classification=classification,
        currency=Currency(code=currency),
        lines=lines,
    )


def _income_statement(
    *,
    scope: LedgerScope,
    revenue_lines: tuple[IncomeStatementLine, ...],
    expense_lines: tuple[IncomeStatementLine, ...],
) -> IncomeStatement:
    return IncomeStatement(
        scope=scope,
        revenues=_is_section(AccountClassification.REVENUE, revenue_lines, scope.currency.code),
        expenses=_is_section(AccountClassification.EXPENSE, expense_lines, scope.currency.code),
    )


def test_financial_statements_empty_exercise_is_valid() -> None:
    scope = _scope()
    balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0"),
            expense_total=_money("0"),
        ),
        assets_lines=(),
        liabilities_lines=(),
        equity_lines=(),
    )
    income_statement = _income_statement(scope=scope, revenue_lines=(), expense_lines=())

    statements = FinancialStatements(
        balance_sheet=balance_sheet,
        income_statement=income_statement,
    )

    assert statements.balance_sheet == balance_sheet
    assert statements.income_statement == income_statement


def test_financial_statements_profitable_exercise_is_valid() -> None:
    scope = _scope()
    balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("50.00"),
            expense_total=_money("20.00"),
        ),
        assets_lines=(
            _bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),
        ),
        liabilities_lines=(
            _bs_line(
                "2000",
                AccountClassification.LIABILITY,
                DebitCreditSide.CREDIT,
                "70.00",
            ),
        ),
        equity_lines=(),
    )
    income_statement = _income_statement(
        scope=scope,
        revenue_lines=(
            _is_line(
                "4000",
                AccountClassification.REVENUE,
                DebitCreditSide.CREDIT,
                "50.00",
            ),
        ),
        expense_lines=(
            _is_line(
                "5000",
                AccountClassification.EXPENSE,
                DebitCreditSide.DEBIT,
                "20.00",
            ),
        ),
    )

    statements = FinancialStatements(
        balance_sheet=balance_sheet,
        income_statement=income_statement,
    )

    assert statements.income_statement.net_result_side() is DebitCreditSide.CREDIT
    assert statements.income_statement.net_result_amount() == _money("30.00")


def test_financial_statements_loss_exercise_is_valid() -> None:
    scope = _scope()
    balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("15.00"),
            expense_total=_money("20.00"),
        ),
        assets_lines=(
            _bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "95.00"),
        ),
        liabilities_lines=(
            _bs_line(
                "2000",
                AccountClassification.LIABILITY,
                DebitCreditSide.CREDIT,
                "40.00",
            ),
        ),
        equity_lines=(
            _bs_line("3000", AccountClassification.EQUITY, DebitCreditSide.CREDIT, "60.00"),
        ),
    )
    income_statement = _income_statement(
        scope=scope,
        revenue_lines=(
            _is_line(
                "4000",
                AccountClassification.REVENUE,
                DebitCreditSide.CREDIT,
                "15.00",
            ),
        ),
        expense_lines=(
            _is_line(
                "5000",
                AccountClassification.EXPENSE,
                DebitCreditSide.DEBIT,
                "20.00",
            ),
        ),
    )

    statements = FinancialStatements(
        balance_sheet=balance_sheet,
        income_statement=income_statement,
    )

    assert statements.income_statement.net_result_side() is DebitCreditSide.DEBIT
    assert statements.income_statement.net_result_amount() == _money("5.00")


def test_financial_statements_rejects_scope_legal_entity_mismatch() -> None:
    balance_scope = _scope(legal_entity_id="entity-01")
    income_scope = _scope(legal_entity_id="entity-02")
    balance_sheet = _balance_sheet(
        scope=balance_scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0"),
            expense_total=_money("0"),
        ),
        assets_lines=(),
        liabilities_lines=(),
        equity_lines=(),
    )
    income_statement = _income_statement(scope=income_scope, revenue_lines=(), expense_lines=())

    with pytest.raises(FinancialStatementsScopeMismatchError):
        FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )


def test_financial_statements_rejects_scope_fiscal_year_mismatch() -> None:
    balance_scope = _scope(fiscal_year=2026)
    income_scope = _scope(fiscal_year=2027)
    balance_sheet = _balance_sheet(
        scope=balance_scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0"),
            expense_total=_money("0"),
        ),
        assets_lines=(),
        liabilities_lines=(),
        equity_lines=(),
    )
    income_statement = _income_statement(scope=income_scope, revenue_lines=(), expense_lines=())

    with pytest.raises(FinancialStatementsScopeMismatchError):
        FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )


def test_financial_statements_rejects_scope_currency_mismatch() -> None:
    balance_scope = _scope(currency="CHF")
    income_scope = _scope(currency="EUR")
    balance_sheet = _balance_sheet(
        scope=balance_scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0"),
            expense_total=_money("0"),
        ),
        assets_lines=(),
        liabilities_lines=(),
        equity_lines=(),
    )
    income_statement = _income_statement(scope=income_scope, revenue_lines=(), expense_lines=())

    with pytest.raises(FinancialStatementsScopeMismatchError):
        FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )


def test_financial_statements_rejects_current_period_result_currency_mismatch() -> None:
    scope = _scope(currency="CHF")
    valid_balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0", currency="CHF"),
            expense_total=_money("0", currency="CHF"),
        ),
        assets_lines=(),
        liabilities_lines=(),
        equity_lines=(),
    )
    broken_balance_sheet = object.__new__(BalanceSheet)
    object.__setattr__(broken_balance_sheet, "scope", valid_balance_sheet.scope)
    object.__setattr__(broken_balance_sheet, "assets", valid_balance_sheet.assets)
    object.__setattr__(broken_balance_sheet, "liabilities", valid_balance_sheet.liabilities)
    object.__setattr__(broken_balance_sheet, "equity", valid_balance_sheet.equity)
    object.__setattr__(
        broken_balance_sheet,
        "current_period_result",
        CurrentPeriodResult(
            currency=Currency(code="EUR"),
            revenue_total=_money("0", currency="EUR"),
            expense_total=_money("0", currency="EUR"),
        ),
    )
    income_statement = _income_statement(scope=scope, revenue_lines=(), expense_lines=())

    with pytest.raises(FinancialStatementsCurrencyMismatchError):
        FinancialStatements(
            balance_sheet=broken_balance_sheet,
            income_statement=income_statement,
        )


def test_financial_statements_rejects_net_result_side_mismatch() -> None:
    scope = _scope()
    balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("20.00"),
            expense_total=_money("30.00"),
        ),
        assets_lines=(
            _bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "90.00"),
        ),
        liabilities_lines=(
            _bs_line(
                "2000",
                AccountClassification.LIABILITY,
                DebitCreditSide.CREDIT,
                "40.00",
            ),
        ),
        equity_lines=(
            _bs_line("3000", AccountClassification.EQUITY, DebitCreditSide.CREDIT, "60.00"),
        ),
    )
    income_statement = _income_statement(
        scope=scope,
        revenue_lines=(
            _is_line(
                "4000",
                AccountClassification.REVENUE,
                DebitCreditSide.CREDIT,
                "40.00",
            ),
        ),
        expense_lines=(
            _is_line(
                "5000",
                AccountClassification.EXPENSE,
                DebitCreditSide.DEBIT,
                "10.00",
            ),
        ),
    )

    with pytest.raises(FinancialStatementsNetResultMismatchError, match="side"):
        FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )


def test_financial_statements_rejects_net_result_amount_mismatch() -> None:
    scope = _scope()
    balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("50.00"),
            expense_total=_money("20.00"),
        ),
        assets_lines=(
            _bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),
        ),
        liabilities_lines=(
            _bs_line(
                "2000",
                AccountClassification.LIABILITY,
                DebitCreditSide.CREDIT,
                "70.00",
            ),
        ),
        equity_lines=(),
    )
    income_statement = _income_statement(
        scope=scope,
        revenue_lines=(
            _is_line(
                "4000",
                AccountClassification.REVENUE,
                DebitCreditSide.CREDIT,
                "45.00",
            ),
        ),
        expense_lines=(
            _is_line(
                "5000",
                AccountClassification.EXPENSE,
                DebitCreditSide.DEBIT,
                "20.00",
            ),
        ),
    )

    with pytest.raises(FinancialStatementsNetResultMismatchError, match="amount"):
        FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )


def test_financial_statements_rejects_income_statement_net_result_currency_mismatch() -> None:
    scope = _scope(currency="CHF")
    balance_sheet = _balance_sheet(
        scope=scope,
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0", currency="CHF"),
            expense_total=_money("0", currency="CHF"),
        ),
        assets_lines=(),
        liabilities_lines=(),
        equity_lines=(),
    )

    class _BrokenIncomeStatement:
        def __init__(self, shared_scope: LedgerScope) -> None:
            self.scope = shared_scope

        def net_result_side(self) -> DebitCreditSide | None:
            return None

        def net_result_amount(self) -> Money:
            return _money("0", currency="EUR")

    with pytest.raises(FinancialStatementsCurrencyMismatchError):
        FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=_BrokenIncomeStatement(scope),  # type: ignore[arg-type]
        )
