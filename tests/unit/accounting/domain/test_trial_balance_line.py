"""Unit tests for TrialBalanceLine."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.trial_balance_line import TrialBalanceLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


def test_trial_balance_line_computes_debit_balance() -> None:
    line = TrialBalanceLine(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        debit_movement=_money("10.00"),
        credit_movement=_money("3.00"),
    )

    assert line.balance_side is DebitCreditSide.DEBIT
    assert line.balance_amount == _money("7.00")


def test_trial_balance_line_computes_credit_balance() -> None:
    line = TrialBalanceLine(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        debit_movement=_money("2.00"),
        credit_movement=_money("5.00"),
    )

    assert line.balance_side is DebitCreditSide.CREDIT
    assert line.balance_amount == _money("3.00")


def test_trial_balance_line_computes_zero_balance() -> None:
    line = TrialBalanceLine(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        debit_movement=_money("5.00"),
        credit_movement=_money("5.00"),
    )

    assert line.balance_side is None
    assert line.balance_amount == _money("0")


def test_trial_balance_line_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency"):
        TrialBalanceLine(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            debit_movement=_money("5.00", currency="CHF"),
            credit_movement=_money("5.00", currency="EUR"),
        )


def test_trial_balance_line_rejects_debit_movement_currency_mismatch() -> None:
    with pytest.raises(ValueError, match="currency"):
        TrialBalanceLine(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            debit_movement=_money("5.00", currency="EUR"),
            credit_movement=_money("5.00", currency="CHF"),
        )


def test_trial_balance_line_rejects_negative_movements() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        TrialBalanceLine(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            debit_movement=_money("-1.00"),
            credit_movement=_money("0"),
        )


def test_trial_balance_line_rejects_negative_credit_movement() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        TrialBalanceLine(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            debit_movement=_money("0"),
            credit_movement=_money("-1.00"),
        )


def test_trial_balance_line_is_frozen_and_uses_slots() -> None:
    line = TrialBalanceLine(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        debit_movement=_money("1.00"),
        credit_movement=_money("1.00"),
    )

    with pytest.raises(FrozenInstanceError):
        type(line).__setattr__(line, "currency", Currency(code="EUR"))

    assert not hasattr(line, "__dict__")
