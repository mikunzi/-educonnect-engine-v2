"""Unit tests for CurrentPeriodResult."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.current_period_result import CurrentPeriodResult
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


def test_current_period_result_profit() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("50.00"),
        expense_total=_money("20.00"),
    )

    assert result.result_side is DebitCreditSide.CREDIT
    assert result.result_amount == _money("30.00")


def test_current_period_result_loss() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("15.00"),
        expense_total=_money("20.00"),
    )

    assert result.result_side is DebitCreditSide.DEBIT
    assert result.result_amount == _money("5.00")


def test_current_period_result_zero() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("15.00"),
        expense_total=_money("15.00"),
    )

    assert result.result_side is None
    assert result.result_amount == _money("0")


def test_current_period_result_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency"):
        CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("15.00", currency="EUR"),
            expense_total=_money("15.00", currency="CHF"),
        )


def test_current_period_result_rejects_negative_totals() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("-1.00"),
            expense_total=_money("0"),
        )

    with pytest.raises(ValueError, match="greater than or equal to 0"):
        CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0"),
            expense_total=_money("-1.00"),
        )


def test_current_period_result_rejects_expense_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency"):
        CurrentPeriodResult(
            currency=Currency(code="CHF"),
            revenue_total=_money("0", currency="CHF"),
            expense_total=_money("0", currency="EUR"),
        )


def test_current_period_result_is_frozen_and_has_slots() -> None:
    result = CurrentPeriodResult(
        currency=Currency(code="CHF"),
        revenue_total=_money("10.00"),
        expense_total=_money("5.00"),
    )

    with pytest.raises(FrozenInstanceError):
        result.currency = Currency(code="EUR")

    assert not hasattr(result, "__dict__")
