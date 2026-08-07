"""Unit tests for TrialBalance use case."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

import educonnect_engine.accounting.application.trial_balance as trial_balance_module
from educonnect_engine.accounting.application.ledger_projection import (
    LedgerProjectionCommand,
    LedgerProjectionResult,
)
from educonnect_engine.accounting.application.trial_balance import (
    TrialBalanceCommand,
    TrialBalanceHandler,
)
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


@dataclass
class _FakeLedgerProjectionHandler:
    result: LedgerProjectionResult
    calls: list[LedgerProjectionCommand]
    raise_on_execute: Exception | None = None

    def execute(self, command: LedgerProjectionCommand) -> LedgerProjectionResult:
        if self.raise_on_execute is not None:
            raise self.raise_on_execute
        self.calls.append(command)
        return self.result


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _line(side: DebitCreditSide, amount: str, line_index: int) -> LedgerLine:
    return LedgerLine(
        journal_entry_id=JournalEntryId(value=f"JE-{line_index}"),
        posting_date=date(2026, 1, 31),
        posted_at=datetime(2026, 1, 31, 10, line_index, tzinfo=UTC),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value=f"REF-{line_index}"),
        account_number=AccountNumber(value="1000" if side is DebitCreditSide.DEBIT else "2000"),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
        line_index=line_index,
    )


def _ledger() -> Ledger:
    scope = _scope()
    account_1000 = LedgerAccount(
        account_number=AccountNumber(value="1000"),
        currency=scope.currency,
        lines=(_line(DebitCreditSide.DEBIT, "10.00", 0),),
    )
    account_2000 = LedgerAccount(
        account_number=AccountNumber(value="2000"),
        currency=scope.currency,
        lines=(_line(DebitCreditSide.CREDIT, "10.00", 1),),
    )
    return Ledger(scope=scope, accounts=(account_1000, account_2000))


def _command() -> TrialBalanceCommand:
    return TrialBalanceCommand(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def test_trial_balance_projects_from_ledger_projection_result() -> None:
    ledger = _ledger()
    ledger_result = LedgerProjectionResult(
        scope=ledger.scope,
        ledger=ledger,
        journal_entry_count=2,
        ledger_line_count=2,
    )
    projection_handler = _FakeLedgerProjectionHandler(result=ledger_result, calls=[])
    handler = TrialBalanceHandler(ledger_projection_handler=projection_handler)

    result = handler.execute(_command())

    assert result.scope == ledger.scope
    assert result.journal_entry_count == 2
    assert result.ledger_line_count == 2
    assert result.trial_balance_line_count == 2
    assert result.trial_balance.is_balanced() is True
    assert len(projection_handler.calls) == 1


def test_trial_balance_propagates_ledger_projection_error() -> None:
    ledger = _ledger()
    ledger_result = LedgerProjectionResult(
        scope=ledger.scope,
        ledger=ledger,
        journal_entry_count=2,
        ledger_line_count=2,
    )
    projection_handler = _FakeLedgerProjectionHandler(
        result=ledger_result,
        calls=[],
        raise_on_execute=RuntimeError("projection failure"),
    )
    handler = TrialBalanceHandler(ledger_projection_handler=projection_handler)

    with pytest.raises(RuntimeError, match="projection failure"):
        handler.execute(_command())


def test_trial_balance_module_has_no_sqlite_dependency() -> None:
    source = inspect.getsource(trial_balance_module)
    assert "sqlite3" not in source
    assert "infrastructure.sqlite" not in source
