"""Unit tests for LedgerLine value object."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.ledger_line import LedgerLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.money import Money


def _line(
    *,
    posted_at: datetime,
    amount: str = "10.00",
    line_index: int = 0,
    description: str = "desc",
) -> LedgerLine:
    return LedgerLine(
        journal_entry_id=JournalEntryId(value="JE-001"),
        posting_date=date(2026, 2, 1),
        posted_at=posted_at,
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        account_number=AccountNumber(value="1000"),
        side=DebitCreditSide.DEBIT,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description=description,
        line_index=line_index,
    )


def test_ledger_line_accepts_utc_posted_at_and_positive_amount() -> None:
    line = _line(posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC), description="  keep me  ")

    assert line.line_index == 0
    assert line.amount.amount == Decimal("10.00")
    assert line.posted_at.tzinfo is UTC
    assert line.description == "  keep me  "


def test_ledger_line_rejects_naive_posted_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _line(posted_at=datetime(2026, 2, 1, 10, 0))


def test_ledger_line_rejects_non_utc_posted_at() -> None:
    with pytest.raises(ValueError, match="UTC"):
        _line(posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=timezone(timedelta(hours=2))))


def test_ledger_line_rejects_negative_line_index() -> None:
    with pytest.raises(ValueError, match="line_index"):
        _line(posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC), line_index=-1)


def test_ledger_line_rejects_non_int_line_index() -> None:
    with pytest.raises(TypeError, match="line_index"):
        _line(posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC), line_index=1.5)  # type: ignore[arg-type]


def test_ledger_line_rejects_non_positive_amount() -> None:
    with pytest.raises(ValueError, match="positive"):
        _line(posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC), amount="0")


def test_ledger_line_is_frozen_and_uses_slots() -> None:
    line = _line(posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC))

    with pytest.raises(FrozenInstanceError):
        type(line).__setattr__(line, "description", "x")

    assert not hasattr(line, "__dict__")
