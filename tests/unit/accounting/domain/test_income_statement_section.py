"""Unit tests for IncomeStatementSection."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.income_statement_line import IncomeStatementLine
from educonnect_engine.accounting.domain.income_statement_section import (
    IncomeStatementSection,
    IncomeStatementSectionDuplicateAccountError,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


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
        balance_amount=_money(amount, currency=currency),
    )


def test_income_statement_section_rejects_non_revenue_expense_classification() -> None:
    with pytest.raises(ValueError, match="classification"):
        IncomeStatementSection(
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            lines=(),
        )


def test_income_statement_section_rejects_line_classification_mismatch() -> None:
    with pytest.raises(ValueError, match="line classification"):
        IncomeStatementSection(
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            lines=(_line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "1.00"),),
        )


def test_income_statement_section_rejects_line_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="line currency"):
        IncomeStatementSection(
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            lines=(
                _line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "1.00", "EUR"),
            ),
        )


def test_income_statement_section_rejects_duplicate_accounts() -> None:
    line = _line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "1.00")

    with pytest.raises(IncomeStatementSectionDuplicateAccountError):
        IncomeStatementSection(
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            lines=(line, line),
        )


def test_income_statement_section_rejects_unordered_accounts() -> None:
    with pytest.raises(ValueError, match="ordered"):
        IncomeStatementSection(
            classification=AccountClassification.EXPENSE,
            currency=Currency(code="CHF"),
            lines=(
                _line("5010", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "1.00"),
                _line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "1.00"),
            ),
        )


def test_income_statement_section_revenue_total_and_side_with_abnormal_debit() -> None:
    section = IncomeStatementSection(
        classification=AccountClassification.REVENUE,
        currency=Currency(code="CHF"),
        lines=(
            _line("4000", AccountClassification.REVENUE, DebitCreditSide.CREDIT, "20.00"),
            _line("4010", AccountClassification.REVENUE, DebitCreditSide.DEBIT, "3.00"),
        ),
    )

    assert section.total_side() is DebitCreditSide.CREDIT
    assert section.total_amount() == _money("17.00")


def test_income_statement_section_expense_total_and_side_with_abnormal_credit() -> None:
    section = IncomeStatementSection(
        classification=AccountClassification.EXPENSE,
        currency=Currency(code="CHF"),
        lines=(
            _line("5000", AccountClassification.EXPENSE, DebitCreditSide.DEBIT, "20.00"),
            _line("5010", AccountClassification.EXPENSE, DebitCreditSide.CREDIT, "3.00"),
        ),
    )

    assert section.total_side() is DebitCreditSide.DEBIT
    assert section.total_amount() == _money("17.00")


def test_income_statement_section_total_side_none_when_zero() -> None:
    section = IncomeStatementSection(
        classification=AccountClassification.REVENUE,
        currency=Currency(code="CHF"),
        lines=(_line("4000", AccountClassification.REVENUE, None, "0"),),
    )

    assert section.total_side() is None
    assert section.total_amount() == _money("0")


def test_income_statement_section_revenue_total_side_debit_when_negative() -> None:
    section = IncomeStatementSection(
        classification=AccountClassification.REVENUE,
        currency=Currency(code="CHF"),
        lines=(_line("4000", AccountClassification.REVENUE, DebitCreditSide.DEBIT, "9.00"),),
    )

    assert section.total_side() is DebitCreditSide.DEBIT
    assert section.total_amount() == _money("9.00")


def test_income_statement_section_expense_total_side_credit_when_negative() -> None:
    section = IncomeStatementSection(
        classification=AccountClassification.EXPENSE,
        currency=Currency(code="CHF"),
        lines=(_line("5000", AccountClassification.EXPENSE, DebitCreditSide.CREDIT, "9.00"),),
    )

    assert section.total_side() is DebitCreditSide.CREDIT
    assert section.total_amount() == _money("9.00")
