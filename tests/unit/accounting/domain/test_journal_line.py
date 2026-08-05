"""Unit tests for JournalLine value object."""

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money


def test_journal_line_creation_success() -> None:
    line = JournalLine(
        account_number=AccountNumber(value="1000"),
        side=DebitCreditSide.DEBIT,
        amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
        description="Tuition invoice",
    )

    assert line.account_number == AccountNumber(value="1000")
    assert line.side == DebitCreditSide.DEBIT
    assert line.amount.amount == Decimal("10.00")
    assert line.amount.currency == Currency(code="CHF")
    assert line.description == "Tuition invoice"


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-1.00")])
def test_journal_line_rejects_non_positive_amount(amount: Decimal) -> None:
    with pytest.raises(ValueError):
        JournalLine(
            account_number=AccountNumber(value="1000"),
            side=DebitCreditSide.DEBIT,
            amount=Money(amount=amount, currency=Currency(code="CHF")),
            description="desc",
        )


def test_journal_line_rejects_blank_description() -> None:
    with pytest.raises(ValueError):
        JournalLine(
            account_number=AccountNumber(value="1000"),
            side=DebitCreditSide.CREDIT,
            amount=Money(amount=Decimal("1.00"), currency=Currency(code="CHF")),
            description="   ",
        )


def test_journal_line_rejects_invalid_account_number_type() -> None:
    with pytest.raises(TypeError):
        JournalLine(
            account_number="1000",  # type: ignore[arg-type]
            side=DebitCreditSide.DEBIT,
            amount=Money(amount=Decimal("1.00"), currency=Currency(code="CHF")),
            description="desc",
        )


def test_journal_line_rejects_invalid_side_type() -> None:
    with pytest.raises(TypeError):
        JournalLine(
            account_number=AccountNumber(value="1000"),
            side="debit",  # type: ignore[arg-type]
            amount=Money(amount=Decimal("1.00"), currency=Currency(code="CHF")),
            description="desc",
        )


def test_journal_line_rejects_invalid_amount_type() -> None:
    with pytest.raises(TypeError):
        JournalLine(
            account_number=AccountNumber(value="1000"),
            side=DebitCreditSide.DEBIT,
            amount="1.00",  # type: ignore[arg-type]
            description="desc",
        )


def test_journal_line_is_frozen_and_has_slots() -> None:
    line = JournalLine(
        account_number=AccountNumber(value="1000"),
        side=DebitCreditSide.DEBIT,
        amount=Money(amount=Decimal("1.00"), currency=Currency(code="CHF")),
        description="desc",
    )

    with pytest.raises(FrozenInstanceError):
        type(line).__setattr__(line, "description", "updated")

    assert not hasattr(line, "__dict__")
