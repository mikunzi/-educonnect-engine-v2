"""Unit tests for TrialBalance."""

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
from educonnect_engine.accounting.domain.trial_balance import (
    TrialBalance,
    TrialBalanceAccountOrderError,
    TrialBalanceCurrencyMismatchError,
    TrialBalanceDuplicateAccountError,
    TrialBalanceUnbalancedTotalsError,
)
from educonnect_engine.accounting.domain.trial_balance_line import TrialBalanceLine
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


def _tb_line(account: str, debit: str, credit: str, currency: str = "CHF") -> TrialBalanceLine:
    return TrialBalanceLine(
        account_number=AccountNumber(value=account),
        currency=Currency(code=currency),
        debit_movement=Money(amount=Decimal(debit), currency=Currency(code=currency)),
        credit_movement=Money(amount=Decimal(credit), currency=Currency(code=currency)),
    )


def _ledger_line(
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


def test_trial_balance_accepts_empty_lines() -> None:
    tb = TrialBalance(scope=_scope(), lines=())

    assert tb.lines == ()
    assert tb.total_debit() == Money(amount=Decimal("0"), currency=Currency(code="CHF"))
    assert tb.total_credit() == Money(amount=Decimal("0"), currency=Currency(code="CHF"))
    assert tb.is_balanced() is True


def test_trial_balance_totals_and_get_line() -> None:
    line_1000 = _tb_line("1000", "10.00", "0")
    line_2000 = _tb_line("2000", "0", "10.00")
    tb = TrialBalance(scope=_scope(), lines=(line_1000, line_2000))

    assert tb.get_line(AccountNumber(value="1000")) == line_1000
    assert tb.get_line(AccountNumber(value="9999")) is None
    assert tb.total_debit() == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))
    assert tb.total_credit() == Money(amount=Decimal("10.00"), currency=Currency(code="CHF"))
    assert tb.is_balanced() is True


def test_trial_balance_rejects_duplicate_accounts() -> None:
    line = _tb_line("1000", "5.00", "5.00")

    with pytest.raises(TrialBalanceDuplicateAccountError):
        TrialBalance(scope=_scope(), lines=(line, line))


def test_trial_balance_rejects_unsorted_accounts() -> None:
    line_1000 = _tb_line("1000", "5.00", "5.00")
    line_2000 = _tb_line("2000", "5.00", "5.00")

    with pytest.raises(TrialBalanceAccountOrderError):
        TrialBalance(scope=_scope(), lines=(line_2000, line_1000))


def test_trial_balance_rejects_line_currency_mismatch_scope() -> None:
    with pytest.raises(TrialBalanceCurrencyMismatchError):
        TrialBalance(
            scope=_scope(currency="CHF"),
            lines=(_tb_line("1000", "5.00", "5.00", "EUR"),),
        )


def test_trial_balance_rejects_unbalanced_totals() -> None:
    with pytest.raises(TrialBalanceUnbalancedTotalsError):
        TrialBalance(scope=_scope(), lines=(_tb_line("1000", "10.00", "0"),))


def test_trial_balance_can_be_built_from_ledger_lines() -> None:
    account_1000 = _ledger_account(
        "1000",
        (
            _ledger_line("1000", DebitCreditSide.DEBIT, "10.00", 0, "JE-001"),
        ),
    )
    account_2000 = _ledger_account(
        "2000",
        (
            _ledger_line("2000", DebitCreditSide.CREDIT, "10.00", 1, "JE-001"),
        ),
    )
    ledger = Ledger(scope=_scope(), accounts=(account_1000, account_2000))

    line_1000 = TrialBalanceLine(
        account_number=account_1000.account_number,
        currency=ledger.scope.currency,
        debit_movement=account_1000.total_debit,
        credit_movement=account_1000.total_credit,
    )
    line_2000 = TrialBalanceLine(
        account_number=account_2000.account_number,
        currency=ledger.scope.currency,
        debit_movement=account_2000.total_debit,
        credit_movement=account_2000.total_credit,
    )

    tb = TrialBalance(scope=ledger.scope, lines=(line_1000, line_2000))
    assert tb.is_balanced() is True
