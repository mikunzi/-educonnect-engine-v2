"""Unit tests for Ledger projection aggregate."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.ledger import Ledger
from educonnect_engine.accounting.domain.ledger_account import LedgerAccount
from educonnect_engine.accounting.domain.ledger_line import LedgerLine
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _scope(currency: str = "CHF") -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code=currency),
    )


def _line(
    *,
    account: str,
    side: DebitCreditSide,
    amount: str,
    posting_date: date,
    posted_at: datetime,
    line_index: int,
    entry_id: str,
    currency: str = "CHF",
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


def _account(
    account_number: str,
    lines: tuple[LedgerLine, ...],
    currency: str = "CHF",
) -> LedgerAccount:
    return LedgerAccount(
        account_number=AccountNumber(value=account_number),
        currency=Currency(code=currency),
        lines=lines,
    )


def test_ledger_accepts_empty_accounts_with_explicit_scope() -> None:
    ledger = Ledger(scope=_scope(), accounts=())

    assert ledger.scope == _scope()
    assert ledger.accounts == ()
    assert ledger.total_debit() == Money(amount=Decimal("0"), currency=Currency(code="CHF"))
    assert ledger.total_credit() == Money(amount=Decimal("0"), currency=Currency(code="CHF"))
    assert ledger.lines() == ()


def test_ledger_get_account_lines_and_totals() -> None:
    line_a = _line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="10.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=0,
        entry_id="JE-001",
    )
    line_b = _line(
        account="2000",
        side=DebitCreditSide.CREDIT,
        amount="10.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=1,
        entry_id="JE-001",
    )

    account_1000 = _account("1000", (line_a,))
    account_2000 = _account("2000", (line_b,))
    ledger = Ledger(scope=_scope(), accounts=(account_1000, account_2000))

    assert ledger.get_account(AccountNumber(value="1000")) == account_1000
    assert ledger.get_account(AccountNumber(value="9999")) is None
    assert ledger.lines() == (line_a, line_b)
    assert ledger.total_debit() == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))
    assert ledger.total_credit() == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))


def test_ledger_rejects_duplicate_accounts() -> None:
    line = _line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="1.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=0,
        entry_id="JE-001",
    )
    account = _account("1000", (line,))

    with pytest.raises(ValueError, match="duplicate"):
        Ledger(scope=_scope(), accounts=(account, account))


def test_ledger_rejects_unsorted_accounts() -> None:
    line_1000 = _line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="1.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=0,
        entry_id="JE-001",
    )
    line_2000 = _line(
        account="2000",
        side=DebitCreditSide.CREDIT,
        amount="1.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=1,
        entry_id="JE-001",
    )

    with pytest.raises(ValueError, match="ordered"):
        Ledger(
            scope=_scope(),
            accounts=(
                _account("2000", (line_2000,)),
                _account("1000", (line_1000,)),
            ),
        )


def test_ledger_rejects_account_currency_mismatch_with_scope() -> None:
    line = _line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="1.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=0,
        entry_id="JE-001",
        currency="EUR",
    )

    with pytest.raises(ValueError, match="scope"):
        Ledger(scope=_scope(currency="CHF"), accounts=(_account("1000", (line,), currency="EUR"),))


def test_ledger_lines_returns_global_deterministic_order() -> None:
    l1 = _line(
        account="3000",
        side=DebitCreditSide.DEBIT,
        amount="3.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
        line_index=0,
        entry_id="JE-001",
    )
    l2 = _line(
        account="2000",
        side=DebitCreditSide.CREDIT,
        amount="3.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        line_index=0,
        entry_id="JE-002",
    )
    l3 = _line(
        account="1000",
        side=DebitCreditSide.DEBIT,
        amount="1.00",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        line_index=1,
        entry_id="JE-002",
    )

    # Intentionally place lines into per-account buckets where concatenation order
    # would differ from deterministic global order if not re-sorted.
    account_1000 = _account("1000", (l3,))
    account_2000 = _account("2000", (l2,))
    account_3000 = _account("3000", (l1,))
    ledger = Ledger(scope=_scope(), accounts=(account_1000, account_2000, account_3000))

    assert ledger.lines() == (l1, l2, l3)
