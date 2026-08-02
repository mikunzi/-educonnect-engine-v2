"""Unit tests for BalanceSheetSection."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet_line import BalanceSheetLine
from educonnect_engine.accounting.domain.balance_sheet_section import (
    BalanceSheetSection,
    BalanceSheetSectionDuplicateAccountError,
)
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
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
) -> BalanceSheetLine:
    return BalanceSheetLine(
        account_number=AccountNumber(value=account),
        classification=classification,
        currency=Currency(code=currency),
        balance_side=side,
        balance_amount=_money(amount, currency=currency),
    )


def test_balance_sheet_section_rejects_non_balance_sheet_classification() -> None:
    with pytest.raises(ValueError, match="classification"):
        BalanceSheetSection(
            classification=AccountClassification.REVENUE,
            currency=Currency(code="CHF"),
            lines=(),
        )


def test_balance_sheet_section_rejects_line_classification_mismatch() -> None:
    with pytest.raises(ValueError, match="line classification"):
        BalanceSheetSection(
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            lines=(
                _line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "5.00"),
            ),
        )


def test_balance_sheet_section_rejects_duplicate_accounts() -> None:
    line = _line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "5.00")

    with pytest.raises(BalanceSheetSectionDuplicateAccountError):
        BalanceSheetSection(
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            lines=(line, line),
        )


def test_balance_sheet_section_rejects_line_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="line currency"):
        BalanceSheetSection(
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            lines=(
                _line(
                    "1000",
                    AccountClassification.ASSET,
                    DebitCreditSide.DEBIT,
                    "1.00",
                    currency="EUR",
                ),
            ),
        )


def test_balance_sheet_section_rejects_unordered_accounts() -> None:
    with pytest.raises(ValueError, match="ordered"):
        BalanceSheetSection(
            classification=AccountClassification.ASSET,
            currency=Currency(code="CHF"),
            lines=(
                _line("1010", AccountClassification.ASSET, DebitCreditSide.DEBIT, "1.00"),
                _line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "1.00"),
            ),
        )


def test_balance_sheet_section_asset_totals_handle_abnormal_credit() -> None:
    section = BalanceSheetSection(
        classification=AccountClassification.ASSET,
        currency=Currency(code="CHF"),
        lines=(
            _line("1000", AccountClassification.ASSET, DebitCreditSide.DEBIT, "20.00"),
            _line("1010", AccountClassification.ASSET, DebitCreditSide.CREDIT, "3.00"),
        ),
    )

    assert section.total_side() is DebitCreditSide.DEBIT
    assert section.total_amount() == _money("17.00")


def test_balance_sheet_section_liability_totals_handle_abnormal_debit() -> None:
    section = BalanceSheetSection(
        classification=AccountClassification.LIABILITY,
        currency=Currency(code="CHF"),
        lines=(
            _line("2000", AccountClassification.LIABILITY, DebitCreditSide.CREDIT, "20.00"),
            _line("2010", AccountClassification.LIABILITY, DebitCreditSide.DEBIT, "3.00"),
        ),
    )

    assert section.total_side() is DebitCreditSide.CREDIT
    assert section.total_amount() == _money("17.00")


def test_balance_sheet_section_asset_total_side_credit_when_negative() -> None:
    section = BalanceSheetSection(
        classification=AccountClassification.ASSET,
        currency=Currency(code="CHF"),
        lines=(
            _line("1000", AccountClassification.ASSET, DebitCreditSide.CREDIT, "9.00"),
        ),
    )

    assert section.total_side() is DebitCreditSide.CREDIT
    assert section.total_amount() == _money("9.00")


def test_balance_sheet_section_liability_total_side_debit_when_negative() -> None:
    section = BalanceSheetSection(
        classification=AccountClassification.LIABILITY,
        currency=Currency(code="CHF"),
        lines=(
            _line("2000", AccountClassification.LIABILITY, DebitCreditSide.DEBIT, "9.00"),
        ),
    )

    assert section.total_side() is DebitCreditSide.DEBIT
    assert section.total_amount() == _money("9.00")


def test_balance_sheet_section_total_side_none_when_zero() -> None:
    section = BalanceSheetSection(
        classification=AccountClassification.ASSET,
        currency=Currency(code="CHF"),
        lines=(
            _line("1000", AccountClassification.ASSET, None, "0"),
        ),
    )

    assert section.total_side() is None
    assert section.total_amount() == _money("0")
