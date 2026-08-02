"""Unit tests for TrialBalanceProjectionService."""

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
from educonnect_engine.accounting.domain.trial_balance import TrialBalanceCurrencyMismatchError
from educonnect_engine.accounting.domain.trial_balance_projection_service import (
    TrialBalanceProjectionService,
)
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


def _ledger_line(
    *,
    account: str,
    side: DebitCreditSide,
    amount: str,
    index: int,
    entry_id: str,
    currency: str = "CHF",
) -> LedgerLine:
    return LedgerLine(
        journal_entry_id=JournalEntryId(value=entry_id),
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code=currency)),
        description="line",
        line_index=index,
    )


def _ledger_account(
    account: str,
    lines: tuple[LedgerLine, ...],
    currency: str = "CHF",
) -> LedgerAccount:
    return LedgerAccount(
        account_number=AccountNumber(value=account),
        currency=Currency(code=currency),
        lines=lines,
    )


def test_project_returns_empty_trial_balance_for_empty_ledger() -> None:
    service = TrialBalanceProjectionService()
    ledger = Ledger(scope=_scope(), accounts=())

    tb = service.project(ledger=ledger)

    assert tb.scope == ledger.scope
    assert tb.lines == ()
    assert tb.is_balanced() is True


def test_project_builds_balanced_trial_balance() -> None:
    service = TrialBalanceProjectionService()
    account_1000 = _ledger_account(
        "1000",
        (
            _ledger_line(
                account="1000",
                side=DebitCreditSide.DEBIT,
                amount="10.00",
                index=0,
                entry_id="JE-001",
            ),
            _ledger_line(
                account="1000",
                side=DebitCreditSide.CREDIT,
                amount="2.00",
                index=1,
                entry_id="JE-001",
            ),
        ),
    )
    account_2000 = _ledger_account(
        "2000",
        (
            _ledger_line(
                account="2000",
                side=DebitCreditSide.CREDIT,
                amount="8.00",
                index=0,
                entry_id="JE-002",
            ),
        ),
    )
    ledger = Ledger(scope=_scope(), accounts=(account_1000, account_2000))

    tb = service.project(ledger=ledger)

    assert tuple(line.account_number.value for line in tb.lines) == ("1000", "2000")
    assert tb.total_debit() == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))
    assert tb.total_credit() == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))
    assert tb.is_balanced() is True


def test_project_is_deterministic_for_same_ledger() -> None:
    service = TrialBalanceProjectionService()
    account_1000 = _ledger_account(
        "1000",
        (
            _ledger_line(
                account="1000",
                side=DebitCreditSide.DEBIT,
                amount="4.00",
                index=0,
                entry_id="JE-001",
            ),
            _ledger_line(
                account="1000",
                side=DebitCreditSide.CREDIT,
                amount="4.00",
                index=1,
                entry_id="JE-001",
            ),
        ),
    )
    ledger = Ledger(scope=_scope(), accounts=(account_1000,))

    first = service.project(ledger=ledger)
    second = service.project(ledger=ledger)

    assert first == second


def test_project_does_not_mutate_ledger() -> None:
    service = TrialBalanceProjectionService()
    account_1000 = _ledger_account(
        "1000",
        (
            _ledger_line(
                account="1000",
                side=DebitCreditSide.DEBIT,
                amount="5.00",
                index=0,
                entry_id="JE-001",
            ),
            _ledger_line(
                account="1000",
                side=DebitCreditSide.CREDIT,
                amount="5.00",
                index=1,
                entry_id="JE-001",
            ),
        ),
    )
    ledger = Ledger(scope=_scope(), accounts=(account_1000,))
    before = ledger

    _ = service.project(ledger=ledger)

    assert ledger == before


def test_project_rejects_ledger_currency_mismatch() -> None:
    service = TrialBalanceProjectionService()
    broken_ledger = object.__new__(Ledger)
    object.__setattr__(broken_ledger, "scope", _scope(currency="CHF"))
    object.__setattr__(
        broken_ledger,
        "accounts",
        (
            _ledger_account(
                "1000",
                (
                    _ledger_line(
                        account="1000",
                        side=DebitCreditSide.DEBIT,
                        amount="3.00",
                        index=0,
                        entry_id="JE-001",
                        currency="EUR",
                    ),
                    _ledger_line(
                        account="1000",
                        side=DebitCreditSide.CREDIT,
                        amount="3.00",
                        index=1,
                        entry_id="JE-001",
                        currency="EUR",
                    ),
                ),
                currency="EUR",
            ),
        ),
    )

    with pytest.raises(TrialBalanceCurrencyMismatchError):
        service.project(ledger=broken_ledger)
