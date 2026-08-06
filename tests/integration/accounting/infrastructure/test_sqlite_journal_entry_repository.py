"""Integration tests for SQLiteJournalEntryRepository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.correction_reason import CorrectionReason
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)
from educonnect_engine.accounting.infrastructure.sqlite.mappers.journal_entry_mapper import (
    JournalEntryLineRow,
    JournalEntrySQLiteMapper,
)
from educonnect_engine.accounting.infrastructure.sqlite.repositories import (
    SQLiteJournalEntryRepository,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


class _FailingLineMapper(JournalEntrySQLiteMapper):
    def to_line_rows(self, entry: JournalEntry) -> tuple[JournalEntryLineRow, ...]:
        rows = list(super().to_line_rows(entry))
        rows[0] = JournalEntryLineRow(
            entry_id=f"{entry.id.value}-missing",
            position=rows[0].position,
            account_number=rows[0].account_number,
            side=rows[0].side,
            amount=rows[0].amount,
            currency=rows[0].currency,
            description=rows[0].description,
        )
        return tuple(rows)


def _money(value: str) -> Money:
    return Money(amount=Decimal(value), currency=Currency(code="CHF"))


def _line(account: str, side: DebitCreditSide, amount: str, description: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=_money(amount),
        description=description,
    )


def _recorded_entry(entry_id: str = "JE-2026-001") -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
        legal_entity_id=LegalEntityId(value="acme-ch"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="SA"),
        reference=JournalReference(value=f"REF-{entry_id}"),
        posting_date=date(2026, 1, 15),
        lines=(
            _line("1000", DebitCreditSide.DEBIT, "100.10", "cash"),
            _line("3000", DebitCreditSide.CREDIT, "100.10", "sales"),
        ),
    )


def _bootstrap_v2(db_path: Path) -> None:
    bootstrap = SQLiteSchemaBootstrap(
        connection_factory=ConnectionFactory(),
        config=DatabaseConfig(path=str(db_path)),
        target_version=2,
    )
    bootstrap.bootstrap()


def _new_repository(db_path: Path) -> tuple[SQLiteJournalEntryRepository, sqlite3.Connection]:
    manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    connection = manager.open()
    repository = SQLiteJournalEntryRepository(connection=connection)
    return repository, connection


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(str(db_path)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_add_and_get_by_id_round_trip_preserves_entry_and_lines(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry.db"
    _bootstrap_v2(db_path)
    repository, connection = _new_repository(db_path)

    try:
        entry = _recorded_entry()
        repository.add(entry)

        loaded = repository.get_by_id(entry.id)
        assert loaded is not None
        assert loaded.id == entry.id
        assert loaded.reference == entry.reference
        assert loaded.posting_date == entry.posting_date
        assert loaded.status == entry.status
        assert loaded.currency() == entry.currency()
        assert loaded.lines == entry.lines
        assert loaded.lines[0].description == "cash"
        assert tuple(line.account_number.value for line in loaded.lines) == ("1000", "3000")
        assert str(loaded.lines[0].amount.amount) == "100.10"
        assert loaded.total_debit().amount == loaded.total_credit().amount
    finally:
        connection.close()


def test_get_by_id_unknown_returns_none(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry-unknown.db"
    _bootstrap_v2(db_path)
    repository, connection = _new_repository(db_path)

    try:
        missing = repository.get_by_id(JournalEntryId(value="MISSING-ENTRY"))
        assert missing is None
    finally:
        connection.close()


def test_add_duplicate_raises_error(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry-duplicate.db"
    _bootstrap_v2(db_path)
    repository, connection = _new_repository(db_path)

    try:
        entry = _recorded_entry()
        repository.add(entry)

        try:
            repository.add(entry)
        except ValueError as exc:
            assert "already exists" in str(exc)
        else:
            raise AssertionError("expected duplicate journal entry error")
    finally:
        connection.close()


def test_add_rolls_back_header_when_line_insert_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry-rollback.db"
    _bootstrap_v2(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository._mapper = _FailingLineMapper()  # type: ignore[attr-defined]
        entry = _recorded_entry("JE-2026-ROLLBACK")

        try:
            repository.add(entry)
        except ValueError:
            pass
        else:
            raise AssertionError("expected insertion failure")

        header = connection.execute(
            "SELECT 1 FROM journal_entries WHERE id = ?",
            (entry.id.value,),
        ).fetchone()
        assert header is None
    finally:
        connection.close()


def test_persist_and_reload_reversal_entry(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry-reversal.db"
    _bootstrap_v2(db_path)
    repository, connection = _new_repository(db_path)

    try:
        original = _recorded_entry("JE-2026-ORIGINAL").post(
            posted_at=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
        )
        repository.add(original)

        reversal = original.build_reversal(
            reversal_entry_id=JournalEntryId(value="JE-2026-REV-001"),
            reversal_fiscal_year=FiscalYear(value=2026),
            reversal_journal_code=JournalCode(value="SA"),
            reversal_reference=JournalReference(value="REV-REF-001"),
            reversal_date=date(2026, 1, 20),
            correction_reason=CorrectionReason(value="correction test"),
        ).post(posted_at=datetime(2026, 1, 20, 12, 0, tzinfo=UTC))

        repository.save_reversal(
            reversal_entry=reversal,
            original_entry_id=original.id,
            expected_original_version=original.version,
        )

        loaded = repository.get_by_id(reversal.id)
        assert loaded is not None
        assert loaded.correction_of_entry_id == original.id
        assert loaded.correction_reason is not None
        assert loaded.correction_reason.value == "correction test"
        assert loaded.status == reversal.status
        assert loaded.lines == reversal.lines
    finally:
        connection.close()


def test_can_read_after_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry-reopen.db"
    _bootstrap_v2(db_path)
    repository, connection = _new_repository(db_path)

    entry = _recorded_entry("JE-2026-REOPEN")
    try:
        repository.add(entry)
    finally:
        connection.close()

    reopened_repository, reopened_connection = _new_repository(db_path)
    try:
        loaded = reopened_repository.get_by_id(entry.id)
        assert loaded is not None
        assert loaded.id == entry.id
    finally:
        reopened_connection.close()


def test_schema_contains_only_expected_tables_for_this_phase(tmp_path: Path) -> None:
    db_path = tmp_path / "journal-entry-schema.db"
    _bootstrap_v2(db_path)

    tables = _table_names(db_path)
    assert "schema_migrations" in tables
    assert "journal_entries" in tables
    assert "journal_entry_lines" in tables

    forbidden = {
        "accounts",
        "accounting_periods",
        "year_end_snapshots",
        "opening_entries",
    }
    assert forbidden.isdisjoint(tables)
