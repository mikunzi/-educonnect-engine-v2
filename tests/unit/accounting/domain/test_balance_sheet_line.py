"""Unit tests for BalanceSheetLine."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet_line import BalanceSheetLine
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


def test_balance_sheet_line_asset_contribution_for_debit_balance() -> None:
    line = BalanceSheetLine(
        account_number=AccountNumber(value="1000"),
        classification=AccountClassification.ASSET,
        currency=Currency(code="CHF"),
        balance_side=DebitCreditSide.DEBIT,
        balance_amount=_money("25.00"),
    )

    assert line.contribution_side is DebitCreditSide.DEBIT
    assert line.contribution_amount == _money("25.00")


def test_balance_sheet_line_asset_contribution_for_credit_balance() -> None:
    line = BalanceSheetLine(
        account_number=AccountNumber(value="1000"),
        classification=AccountClassification.ASSET,
        currency=Currency(code="CHF"),
        balance_side=DebitCreditSide.CREDIT,
        balance_amount=_money("5.00"),
    )

    assert line.contribution_side is DebitCreditSide.CREDIT
    assert line.contribution_amount == _money("5.00")


def test_balance_sheet_line_liability_contribution() -> None:
    line = BalanceSheetLine(
        account_number=AccountNumber(value="2000"),
        classification=AccountClassification.LIABILITY,
        currency=Currency(code="CHF"),
        balance_side=DebitCreditSide.CREDIT,
        balance_amount=_money("17.00"),
    )

    assert line.contribution_side is DebitCreditSide.CREDIT
    assert line.contribution_amount == _money("17.00")


def test_balance_sheet_line_zero_balance_has_zero_contribution() -> None:
    line = BalanceSheetLine(
        account_number=AccountNumber(value="3000"),
        classification=AccountClassification.EQUITY,
        currency=Currency(code="CHF"),
        balance_side=None,
        balance_amount=_money("0"),
    )

    assert line.contribution_side is None
    assert line.contribution_amount == _money("0")


def test_balance_sheet_line_rejects_revenue_or_expense_classification() -> None:
    with pytest.raises(ValueError, match="classification"):
        BalanceSheetLine(
            account_number=AccountNumber(value="4000"),
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            balance_side=DebitCreditSide.CREDIT,
            balance_amount=_money("10.00"),
        )


def test_balance_sheet_line_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency"):
        BalanceSheetLine(
            account_number=AccountNumber(value="1000"),
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            balance_side=DebitCreditSide.DEBIT,
            balance_amount=_money("10.00", currency="EUR"),
        )


def test_balance_sheet_line_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        BalanceSheetLine(
            account_number=AccountNumber(value="1000"),
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            balance_side=DebitCreditSide.DEBIT,
            balance_amount=_money("-0.01"),
        )


def test_balance_sheet_line_rejects_none_side_with_non_zero_amount() -> None:
    with pytest.raises(ValueError, match="balance side"):
        BalanceSheetLine(
            account_number=AccountNumber(value="1000"),
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            balance_side=None,
            balance_amount=_money("1.00"),
        )
