"""Unit tests for LedgerProjection use case."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

import educonnect_engine.accounting.application.ledger_projection as ledger_projection_module
from educonnect_engine.accounting.application.ledger_projection import (
    LedgerProjectionCommand,
    LedgerProjectionHandler,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.repositories import LedgerProjectionRepository
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _FakeLedgerProjectionRepository(LedgerProjectionRepository):
    entries: tuple[JournalEntry, ...]
    calls: list[LedgerScope]
    raise_on_get: Exception | None = None

    def get_posted_entries(self, scope: LedgerScope) -> tuple[JournalEntry, ...]:
        if self.raise_on_get is not None:
            raise self.raise_on_get
        self.calls.append(scope)
        return self.entries


@dataclass
class _FakeLedgerProjectionUnitOfWork:
    ledger_projection_repository: _FakeLedgerProjectionRepository
    fail_commit: bool = False
    entered: int = 0
    commit_calls: int = 0
    rollback_calls: int = 0
    close_calls: int = 0
    active: bool = False

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self.active:
            raise RuntimeError("transaction already active")

        self.active = True
        self.entered += 1
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise
        finally:
            self.close()

    def commit(self) -> None:
        if not self.active:
            raise RuntimeError("transaction is not active")
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        if not self.active:
            raise RuntimeError("transaction is not active")
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1
        self.active = False


def _line(side: DebitCreditSide, amount: str, account: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
    )


def _posted_entry(entry_id: str, posted_at_hour: int) -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value=f"REF-{entry_id}"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line(DebitCreditSide.DEBIT, "10.00", "1000"),
            _line(DebitCreditSide.CREDIT, "10.00", "2000"),
        ),
    ).post(posted_at=datetime(2026, 1, 31, posted_at_hour, 0, tzinfo=UTC))


def _command() -> LedgerProjectionCommand:
    return LedgerProjectionCommand(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def test_ledger_projection_projects_entries_and_commits() -> None:
    repository = _FakeLedgerProjectionRepository(
        entries=(_posted_entry("JE-001", 9), _posted_entry("JE-002", 10)),
        calls=[],
    )
    uow = _FakeLedgerProjectionUnitOfWork(ledger_projection_repository=repository)
    handler = LedgerProjectionHandler(uow=uow)

    result = handler.execute(_command())

    assert result.scope.legal_entity_id == LegalEntityId(value="entity-01")
    assert result.journal_entry_count == 2
    assert result.ledger_line_count == 4
    assert len(result.ledger.accounts) == 2
    assert len(repository.calls) == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0
    assert uow.close_calls == 1


def test_ledger_projection_returns_empty_ledger_when_no_entries() -> None:
    repository = _FakeLedgerProjectionRepository(entries=(), calls=[])
    uow = _FakeLedgerProjectionUnitOfWork(ledger_projection_repository=repository)
    handler = LedgerProjectionHandler(uow=uow)

    result = handler.execute(_command())

    assert result.journal_entry_count == 0
    assert result.ledger_line_count == 0
    assert result.ledger.accounts == ()


def test_ledger_projection_rolls_back_on_repository_error() -> None:
    repository = _FakeLedgerProjectionRepository(
        entries=(),
        calls=[],
        raise_on_get=RuntimeError("repository failure"),
    )
    uow = _FakeLedgerProjectionUnitOfWork(ledger_projection_repository=repository)
    handler = LedgerProjectionHandler(uow=uow)

    with pytest.raises(RuntimeError, match="repository failure"):
        handler.execute(_command())

    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_ledger_projection_rolls_back_on_commit_error() -> None:
    repository = _FakeLedgerProjectionRepository(entries=(_posted_entry("JE-001", 9),), calls=[])
    uow = _FakeLedgerProjectionUnitOfWork(
        ledger_projection_repository=repository,
        fail_commit=True,
    )
    handler = LedgerProjectionHandler(uow=uow)

    with pytest.raises(RuntimeError, match="commit failed"):
        handler.execute(_command())

    assert uow.commit_calls == 1
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_ledger_projection_module_has_no_sqlite_dependency() -> None:
    source = inspect.getsource(ledger_projection_module)
    assert "sqlite3" not in source
    assert "infrastructure.sqlite" not in source
