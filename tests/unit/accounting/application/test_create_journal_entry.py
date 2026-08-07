"""Unit tests for CreateJournalEntry use case."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

import educonnect_engine.accounting.application.create_journal_entry as create_journal_entry_module
from educonnect_engine.accounting.application.create_journal_entry import (
    CreateJournalEntryCommand,
    CreateJournalEntryHandler,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.repositories import JournalEntryRepository
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _FakeJournalEntryRepository(JournalEntryRepository):
    added_entries: list[JournalEntry]
    raise_on_add: Exception | None = None

    def add(self, entry: JournalEntry) -> None:
        if self.raise_on_add is not None:
            raise self.raise_on_add
        self.added_entries.append(entry)

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        _ = entry_id
        return None

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        _ = (entry, expected_version)

    def save_reversal(
        self,
        reversal_entry: JournalEntry,
        original_entry_id: JournalEntryId,
        expected_original_version: int,
    ) -> None:
        _ = (reversal_entry, original_entry_id, expected_original_version)


@dataclass
class _FakeCreateJournalEntryUnitOfWork:
    journal_entry_repository: _FakeJournalEntryRepository
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


def _line(side: DebitCreditSide, amount: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value="1000"),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
    )


def _command() -> CreateJournalEntryCommand:
    return CreateJournalEntryCommand(
        journal_entry_id=JournalEntryId(value="JE-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line(DebitCreditSide.DEBIT, "10.00"),
            _line(DebitCreditSide.CREDIT, "10.00"),
        ),
    )


def test_create_journal_entry_persists_recorded_entry_and_commits_once() -> None:
    repository = _FakeJournalEntryRepository(added_entries=[])
    uow = _FakeCreateJournalEntryUnitOfWork(journal_entry_repository=repository)
    handler = CreateJournalEntryHandler(uow=uow)

    result = handler.execute(_command())

    assert result.journal_entry_id == JournalEntryId(value="JE-001")
    assert result.status is JournalEntryStatus.RECORDED
    assert result.version == 0
    assert len(repository.added_entries) == 1
    persisted = repository.added_entries[0]
    assert persisted.id == JournalEntryId(value="JE-001")
    assert persisted.status is JournalEntryStatus.RECORDED
    assert persisted.posted_at is None
    assert uow.entered == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0
    assert uow.close_calls == 1


def test_create_journal_entry_rolls_back_on_repository_error() -> None:
    repository = _FakeJournalEntryRepository(
        added_entries=[],
        raise_on_add=RuntimeError("repository failure"),
    )
    uow = _FakeCreateJournalEntryUnitOfWork(journal_entry_repository=repository)
    handler = CreateJournalEntryHandler(uow=uow)

    with pytest.raises(RuntimeError, match="repository failure"):
        handler.execute(_command())

    assert repository.added_entries == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_create_journal_entry_rolls_back_on_commit_error() -> None:
    repository = _FakeJournalEntryRepository(added_entries=[])
    uow = _FakeCreateJournalEntryUnitOfWork(
        journal_entry_repository=repository,
        fail_commit=True,
    )
    handler = CreateJournalEntryHandler(uow=uow)

    with pytest.raises(RuntimeError, match="commit failed"):
        handler.execute(_command())

    assert len(repository.added_entries) == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_create_journal_entry_module_has_no_sqlite_dependency() -> None:
    source = inspect.getsource(create_journal_entry_module)
    assert "sqlite3" not in source
    assert "infrastructure.sqlite" not in source
