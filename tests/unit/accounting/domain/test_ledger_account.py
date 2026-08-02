"""Unit tests for LedgerAccount projection object."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.ledger_account import LedgerAccount
from educonnect_engine.accounting.domain.ledger_line import LedgerLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.money import Money


def _ledger_line(
    *,
    account: str,
    side: DebitCreditSide,
    amount: str,
    line_index: int,
    posted_at: datetime,
    currency: str = "CHF",
    posting_date: date = date(2026, 2, 1),
    entry_id: str = "JE-001",
) -> LedgerLine:
    return LedgerLine(
        journal_entry_id=JournalEntryId(value=entry_id),
        posting_date=posting_date,
        posted_at=posted_at,
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code=currency)),
        description="line",
        line_index=line_index,
    )


def test_ledger_account_computes_totals_and_debit_balance() -> None:
    line_a = _ledger_line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="10.00",
        line_index=0,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    line_b = _ledger_line(
        account="1000",
        side=DebitCreditSide.CREDIT,
        amount="3.00",
        line_index=1,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    account = LedgerAccount(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        lines=(line_a, line_b),
    )

    assert account.total_debit == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))
    assert account.total_credit == Money(amount=Decimal("3.00"), currency=Currency(code="CHF"))
    assert account.balance_side is DebitCreditSide.DEBIT
    assert account.balance_amount == Money(amount=Decimal("7.00"), currency=Currency(code="CHF"))


def test_ledger_account_computes_credit_balance() -> None:
    line_a = _ledger_line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="2.00",
        line_index=0,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    line_b = _ledger_line(
        account="1000",
        side=DebitCreditSide.CREDIT,
        amount="5.00",
        line_index=1,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    account = LedgerAccount(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        lines=(line_a, line_b),
    )

    assert account.balance_side is DebitCreditSide.CREDIT
    assert account.balance_amount == Money(amount=Decimal("3.00"), currency=Currency(code="CHF"))


def test_ledger_account_computes_zero_balance() -> None:
    line_a = _ledger_line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="5.00",
        line_index=0,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    line_b = _ledger_line(
        account="1000",
        side=DebitCreditSide.CREDIT,
        amount="5.00",
        line_index=1,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    account = LedgerAccount(
        account_number=AccountNumber(value="1000"),
        currency=Currency(code="CHF"),
        lines=(line_a, line_b),
    )

    assert account.balance_side is None
    assert account.balance_amount == Money(amount=Decimal("0"), currency=Currency(code="CHF"))


def test_ledger_account_rejects_line_with_different_account_number() -> None:
    line_a = _ledger_line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="5.00",
        line_index=0,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    line_b = _ledger_line(
        account="2000",
        side=DebitCreditSide.CREDIT,
        amount="5.00",
        line_index=1,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="account_number"):
        LedgerAccount(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            lines=(line_a, line_b),
        )


def test_ledger_account_rejects_line_with_different_currency() -> None:
    line_a = _ledger_line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="5.00",
        line_index=0,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        currency="CHF",
    )
    line_b = _ledger_line(
        account="1000",
        side=DebitCreditSide.CREDIT,
        amount="5.00",
        line_index=1,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        currency="EUR",
    )

    with pytest.raises(ValueError, match="currency"):
        LedgerAccount(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            lines=(line_a, line_b),
        )


def test_ledger_account_rejects_non_deterministic_line_order() -> None:
    later = _ledger_line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="5.00",
        line_index=1,
        posted_at=datetime(2026, 2, 2, 10, 0, tzinfo=UTC),
        posting_date=date(2026, 2, 2),
        entry_id="JE-002",
    )
    earlier = _ledger_line(
        account="1000",
        side=DebitCreditSide.CREDIT,
        amount="5.00",
        line_index=0,
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        posting_date=date(2026, 2, 1),
        entry_id="JE-001",
    )

    with pytest.raises(ValueError, match="deterministic"):
        LedgerAccount(
            account_number=AccountNumber(value="1000"),
            currency=Currency(code="CHF"),
            lines=(later, earlier),
        )
