"""Unit tests for FinancialStatementsProjectionService."""

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
    FinancialStatementsNetResultMismatchError,
)
from educonnect_engine.accounting.domain.financial_statements_projection_service import (
    FinancialStatementsProjectionService,
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


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _bs_line(
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


def _is_line(
    account: str,
    classification: AccountClassification,
    side: DebitCreditSide | None,
    amount: str,
) -> IncomeStatementLine:
    return IncomeStatementLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code="CHF"),
        balance_side=side,
        balance_amount=_money(amount),
    )


def _build_valid_components() -> tuple[BalanceSheet, IncomeStatement]:
    scope = _scope()
    balance_sheet = BalanceSheet(
        scope=scope,
        assets=BalanceSheetSection(
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            lines=(_bs_line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "100.00"),),
        ),
        liabilities=BalanceSheetSection(
            classification=AccountClassification.LIABILITY,
            currency=Currency(code="CHF"),
            lines=(
                _bs_line(
                    "2000",
                    AccountClassification.LIABILITY,
                    DebitCreditSide.CREDIT,
                    "70.00",
                ),
            ),
        ),
        equity=BalanceSheetSection(
            classification=AccountClassification.EQUITY,
            currency=Currency(code="CHF"),
            lines=(),
        ),
        current_period_result=CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("50.00"),
            expense_total=_money("20.00"),
        ),
    )
    income_statement = IncomeStatement(
        scope=scope,
        revenues=IncomeStatementSection(
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            lines=(
                _is_line(
                    "4000",
                    AccountClassification.REVENUE,
                    DebitCreditSide.CREDIT,
                    "50.00",
                ),
            ),
        ),
        expenses=IncomeStatementSection(
            classification=AccountClassification.EXPENSE,
            currency=Currency(code="CHF"),
            lines=(
                _is_line(
                    "5000",
                    AccountClassification.EXPENSE,
                    DebitCreditSide.DEBIT,
                    "20.00",
                ),
            ),
        ),
    )
    return balance_sheet, income_statement


def test_projection_service_assembles_without_mutation() -> None:
    balance_sheet, income_statement = _build_valid_components()
    before_balance_sheet = balance_sheet
    before_income_statement = income_statement

    result = FinancialStatementsProjectionService().project(
        balance_sheet=balance_sheet,
        income_statement=income_statement,
    )

    assert isinstance(result, FinancialStatements)
    assert result.balance_sheet == balance_sheet
    assert result.income_statement == income_statement
    assert balance_sheet == before_balance_sheet
    assert income_statement == before_income_statement


def test_projection_service_propagates_consistency_errors() -> None:
    balance_sheet, income_statement = _build_valid_components()
    inconsistent_income_statement = IncomeStatement(
        scope=income_statement.scope,
        revenues=IncomeStatementSection(
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            lines=(
                _is_line(
                    "4000",
                    AccountClassification.REVENUE,
                    DebitCreditSide.CREDIT,
                    "40.00",
                ),
            ),
        ),
        expenses=IncomeStatementSection(
            classification=AccountClassification.EXPENSE,
            currency=Currency(code="CHF"),
            lines=(
                _is_line(
                    "5000",
                    AccountClassification.EXPENSE,
                    DebitCreditSide.DEBIT,
                    "20.00",
                ),
            ),
        ),
    )

    with pytest.raises(FinancialStatementsNetResultMismatchError):
        FinancialStatementsProjectionService().project(
            balance_sheet=balance_sheet,
            income_statement=inconsistent_income_statement,
        )
