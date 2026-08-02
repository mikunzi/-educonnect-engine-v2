"""Unit tests for IncomeStatementLine."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.income_statement_line import IncomeStatementLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


def test_income_statement_line_revenue_contribution_credit() -> None:
    line = IncomeStatementLine(
        account_number=AccountNumber(value="4000"),
        classification=AccountClassification.REVENUE,
        currency=Currency(code="CHF"),
        balance_side=DebitCreditSide.CREDIT,
        balance_amount=_money("10.00"),
    )

    assert line.contribution_side is DebitCreditSide.CREDIT
    assert line.contribution_amount == _money("10.00")


def test_income_statement_line_expense_contribution_debit() -> None:
    line = IncomeStatementLine(
        account_number=AccountNumber(value="5000"),
        classification=AccountClassification.EXPENSE,
        currency=Currency(code="CHF"),
        balance_side=DebitCreditSide.DEBIT,
        balance_amount=_money("4.00"),
    )

    assert line.contribution_side is DebitCreditSide.DEBIT
    assert line.contribution_amount == _money("4.00")


def test_income_statement_line_zero_balance_has_zero_contribution() -> None:
    line = IncomeStatementLine(
        account_number=AccountNumber(value="4000"),
        classification=AccountClassification.REVENUE,
        currency=Currency(code="CHF"),
        balance_side=None,
        balance_amount=_money("0"),
    )

    assert line.contribution_side is None
    assert line.contribution_amount == _money("0")


def test_income_statement_line_rejects_non_revenue_expense_classification() -> None:
    with pytest.raises(ValueError, match="classification"):
        IncomeStatementLine(
            account_number=AccountNumber(value="1000"),
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            balance_side=DebitCreditSide.DEBIT,
            balance_amount=_money("1.00"),
        )


def test_income_statement_line_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency"):
        IncomeStatementLine(
            account_number=AccountNumber(value="4000"),
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            balance_side=DebitCreditSide.CREDIT,
            balance_amount=_money("1.00", currency="EUR"),
        )


def test_income_statement_line_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        IncomeStatementLine(
            account_number=AccountNumber(value="4000"),
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            balance_side=DebitCreditSide.CREDIT,
            balance_amount=_money("-0.01"),
        )


def test_income_statement_line_rejects_none_side_with_non_zero_amount() -> None:
    with pytest.raises(ValueError, match="balance side"):
        IncomeStatementLine(
            account_number=AccountNumber(value="4000"),
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            balance_side=None,
            balance_amount=_money("1.00"),
        )
