"""Unit tests for DeleteDraftJournalEntry use case."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.application import (
    delete_draft_journal_entry as delete_draft_journal_entry_module,
)
from educonnect_engine.accounting.application.delete_draft_journal_entry import (
    ConcurrencyConflictError,
    DeleteDraftJournalEntryCommand,
    DeleteDraftJournalEntryHandler,
    JournalEntryNotDraftError,
    JournalEntryNotFoundError,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
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
    entries: dict[JournalEntryId, JournalEntry]
    delete_calls: list[tuple[JournalEntryId, int]]
    raise_on_get: Exception | None = None
    raise_on_delete: Exception | None = None

    def add(self, entry: JournalEntry) -> None:
        self.entries[entry.id] = entry

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        if self.raise_on_get is not None:
            raise self.raise_on_get
        return self.entries.get(entry_id)

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        _ = (entry, expected_version)

    def save_reversal(
        self,
        reversal_entry: JournalEntry,
        original_entry_id: JournalEntryId,
        expected_original_version: int,
    ) -> None:
        _ = (reversal_entry, original_entry_id, expected_original_version)

    def delete_draft(self, entry_id: JournalEntryId, expected_version: int) -> None:
        if self.raise_on_delete is not None:
            raise self.raise_on_delete
        self.delete_calls.append((entry_id, expected_version))
        self.entries.pop(entry_id, None)


@dataclass
class _FakeDeleteDraftJournalEntryUnitOfWork:
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


def _recorded_entry(entry_id: str = "JE-001", version: int = 0) -> JournalEntry:
    entry = JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
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
    return JournalEntry(
        id=entry.id,
        legal_entity_id=entry.legal_entity_id,
        fiscal_year=entry.fiscal_year,
        journal_code=entry.journal_code,
        reference=entry.reference,
        posting_date=entry.posting_date,
        version=version,
        status=entry.status,
        posted_at=entry.posted_at,
        lines=entry.lines,
    )


def _new_uow(
    entry: JournalEntry | None,
    fail_commit: bool = False,
) -> _FakeDeleteDraftJournalEntryUnitOfWork:
    entries: dict[JournalEntryId, JournalEntry] = {}
    if entry is not None:
        entries[entry.id] = entry
    return _FakeDeleteDraftJournalEntryUnitOfWork(
        journal_entry_repository=_FakeJournalEntryRepository(entries=entries, delete_calls=[]),
        fail_commit=fail_commit,
    )


def test_delete_draft_journal_entry_succeeds_and_persists_deletion() -> None:
    entry = _recorded_entry(version=2)
    uow = _new_uow(entry)
    handler = DeleteDraftJournalEntryHandler(uow=uow)

    result = handler.execute(
        DeleteDraftJournalEntryCommand(
            journal_entry_id=entry.id,
            expected_version=2,
        ),
    )

    assert result.journal_entry_id == entry.id
    assert result.deleted is True
    assert uow.journal_entry_repository.delete_calls == [(entry.id, 2)]
    assert uow.journal_entry_repository.get_by_id(entry.id) is None
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0
    assert uow.close_calls == 1


def test_delete_draft_journal_entry_raises_not_found() -> None:
    uow = _new_uow(entry=None)
    handler = DeleteDraftJournalEntryHandler(uow=uow)

    with pytest.raises(JournalEntryNotFoundError):
        handler.execute(
            DeleteDraftJournalEntryCommand(
                journal_entry_id=JournalEntryId(value="JE-404"),
                expected_version=0,
            ),
        )

    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_delete_draft_journal_entry_raises_not_draft_when_entry_is_posted() -> None:
    recorded = _recorded_entry(version=1)
    posted = recorded.post(posted_at=datetime(2026, 1, 31, 12, 0, tzinfo=UTC))
    uow = _new_uow(posted)
    handler = DeleteDraftJournalEntryHandler(uow=uow)

    with pytest.raises(JournalEntryNotDraftError):
        handler.execute(
            DeleteDraftJournalEntryCommand(
                journal_entry_id=posted.id,
                expected_version=2,
            ),
        )

    assert uow.journal_entry_repository.delete_calls == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_delete_draft_journal_entry_raises_concurrency_conflict() -> None:
    entry = _recorded_entry(version=2)
    uow = _new_uow(entry)
    handler = DeleteDraftJournalEntryHandler(uow=uow)

    with pytest.raises(ConcurrencyConflictError):
        handler.execute(
            DeleteDraftJournalEntryCommand(
                journal_entry_id=entry.id,
                expected_version=1,
            ),
        )

    assert uow.journal_entry_repository.delete_calls == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_delete_draft_journal_entry_rolls_back_on_repository_error() -> None:
    entry = _recorded_entry(version=0)
    uow = _new_uow(entry)
    uow.journal_entry_repository.raise_on_delete = RuntimeError("repository failure")
    handler = DeleteDraftJournalEntryHandler(uow=uow)

    with pytest.raises(RuntimeError, match="repository failure"):
        handler.execute(
            DeleteDraftJournalEntryCommand(
                journal_entry_id=entry.id,
                expected_version=0,
            ),
        )

    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_delete_draft_journal_entry_rolls_back_on_commit_error() -> None:
    entry = _recorded_entry(version=0)
    uow = _new_uow(entry, fail_commit=True)
    handler = DeleteDraftJournalEntryHandler(uow=uow)

    with pytest.raises(RuntimeError, match="commit failed"):
        handler.execute(
            DeleteDraftJournalEntryCommand(
                journal_entry_id=entry.id,
                expected_version=0,
            ),
        )

    assert uow.journal_entry_repository.delete_calls == [(entry.id, 0)]
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_delete_draft_journal_entry_module_has_no_sqlite_dependency() -> None:
    source = inspect.getsource(delete_draft_journal_entry_module)
    assert "sqlite3" not in source
    assert "infrastructure.sqlite" not in source
