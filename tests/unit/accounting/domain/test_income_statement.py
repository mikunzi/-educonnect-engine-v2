"""Unit tests for IncomeStatement."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_line import IncomeStatementLine
from educonnect_engine.accounting.domain.income_statement_section import IncomeStatementSection
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _scope(currency: str = "CHF") -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code=currency),
    )


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


def _line(
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


def _section(
    classification: AccountClassification,
    lines: tuple[IncomeStatementLine, ...],
    currency: str = "CHF",
) -> IncomeStatementSection:
    return IncomeStatementSection(
        classification=classification,
        currency=Currency(code=currency),
        lines=lines,
    )


def test_income_statement_empty_is_valid() -> None:
    statement = IncomeStatement(
        scope=_scope(),
        revenues=_section(AccountClassification.REVENUE, ()),
        expenses=_section(AccountClassification.EXPENSE, ()),
    )

    assert statement.revenue_total() == _money("0")
    assert statement.expense_total() == _money("0")
    assert statement.net_result_side() is None
    assert statement.net_result_amount() == _money("0")


def test_income_statement_profit_representation() -> None:
    statement = IncomeStatement(
        scope=_scope(),
        revenues=_section(
            AccountClassification.REVENUE,
            (_line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "50.00"),),
        ),
        expenses=_section(
            AccountClassification.EXPENSE,
            (_line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "20.00"),),
        ),
    )

    assert statement.net_result_side() is DebitCreditSide.CREDIT
    assert statement.net_result_amount() == _money("30.00")


def test_income_statement_loss_representation() -> None:
    statement = IncomeStatement(
        scope=_scope(),
        revenues=_section(
            AccountClassification.REVENUE,
            (_line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "15.00"),),
        ),
        expenses=_section(
            AccountClassification.EXPENSE,
            (_line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "20.00"),),
        ),
    )

    assert statement.net_result_side() is DebitCreditSide.DEBIT
    assert statement.net_result_amount() == _money("5.00")


def test_income_statement_rejects_wrong_revenue_section_classification() -> None:
    with pytest.raises(ValueError, match="revenues section"):
        IncomeStatement(
            scope=_scope(),
            revenues=_section(AccountClassification.EXPENSE, ()),
            expenses=_section(AccountClassification.EXPENSE, ()),
        )


def test_income_statement_rejects_wrong_expense_section_classification() -> None:
    with pytest.raises(ValueError, match="expenses section"):
        IncomeStatement(
            scope=_scope(),
            revenues=_section(AccountClassification.REVENUE, ()),
            expenses=_section(AccountClassification.REVENUE, ()),
        )


def test_income_statement_rejects_section_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="section currency"):
        IncomeStatement(
            scope=_scope(),
            revenues=_section(AccountClassification.REVENUE, (), currency="EUR"),
            expenses=_section(AccountClassification.EXPENSE, ()),
        )
