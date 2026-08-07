"""Integration tests for SQLiteLedgerProjectionRepository."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)
from educonnect_engine.accounting.infrastructure.sqlite.repositories import (
    SQLiteJournalEntryRepository,
    SQLiteLedgerProjectionRepository,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _bootstrap_v2(db_path: Path) -> None:
    bootstrap = SQLiteSchemaBootstrap(
        connection_factory=ConnectionFactory(),
        config=DatabaseConfig(path=str(db_path)),
        target_version=2,
    )
    bootstrap.bootstrap()


def _line(account: str, side: DebitCreditSide, amount: str, currency: str = "CHF") -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code=currency)),
        description="line",
    )


def _recorded_entry(
    *,
    entry_id: str,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2026,
    currency: str = "CHF",
) -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
        legal_entity_id=LegalEntityId(value=legal_entity_id),
        fiscal_year=FiscalYear(value=fiscal_year),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value=f"REF-{entry_id}"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line("1000", DebitCreditSide.DEBIT, "10.00", currency),
            _line("2000", DebitCreditSide.CREDIT, "10.00", currency),
        ),
    )


def _scope(currency: str = "CHF") -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code=currency),
    )


def _new_repositories(
    db_path: Path,
) -> tuple[SQLiteJournalEntryRepository, SQLiteLedgerProjectionRepository, sqlite3.Connection]:
    manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    connection = manager.open()
    return (
        SQLiteJournalEntryRepository(connection=connection),
        SQLiteLedgerProjectionRepository(connection=connection),
        connection,
    )


def test_get_posted_entries_returns_only_posted_entries_in_scope(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger-projection-posted-only.db"
    _bootstrap_v2(db_path)
    journal_repository, projection_repository, connection = _new_repositories(db_path)

    try:
        posted_a = _recorded_entry(entry_id="JE-001").post(
            posted_at=datetime(2026, 1, 31, 8, 0, tzinfo=UTC),
        )
        posted_b = _recorded_entry(entry_id="JE-002").post(
            posted_at=datetime(2026, 1, 31, 9, 0, tzinfo=UTC),
        )
        recorded = _recorded_entry(entry_id="JE-003")
        other_scope = _recorded_entry(entry_id="JE-004", legal_entity_id="entity-02").post(
            posted_at=datetime(2026, 1, 31, 10, 0, tzinfo=UTC),
        )

        journal_repository.add(posted_b)
        journal_repository.add(recorded)
        journal_repository.add(posted_a)
        journal_repository.add(other_scope)

        entries = projection_repository.get_posted_entries(_scope())

        assert tuple(entry.id.value for entry in entries) == ("JE-001", "JE-002")
        assert all(entry.posted_at is not None for entry in entries)
    finally:
        connection.close()


def test_get_posted_entries_filters_by_currency(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger-projection-currency.db"
    _bootstrap_v2(db_path)
    journal_repository, projection_repository, connection = _new_repositories(db_path)

    try:
        chf_entry = _recorded_entry(entry_id="JE-CHF", currency="CHF").post(
            posted_at=datetime(2026, 1, 31, 8, 0, tzinfo=UTC),
        )
        eur_entry = _recorded_entry(entry_id="JE-EUR", currency="EUR").post(
            posted_at=datetime(2026, 1, 31, 9, 0, tzinfo=UTC),
        )

        journal_repository.add(chf_entry)
        journal_repository.add(eur_entry)

        entries = projection_repository.get_posted_entries(_scope(currency="CHF"))

        assert tuple(entry.id.value for entry in entries) == ("JE-CHF",)
    finally:
        connection.close()


def test_get_posted_entries_survives_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger-projection-reopen.db"
    _bootstrap_v2(db_path)
    journal_repository, _projection_repository, connection = _new_repositories(db_path)

    try:
        posted = _recorded_entry(entry_id="JE-REOPEN").post(
            posted_at=datetime(2026, 1, 31, 8, 0, tzinfo=UTC),
        )
        journal_repository.add(posted)
    finally:
        connection.close()

    reopened_manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    reopened_connection = reopened_manager.open()
    reopened_projection_repository = SQLiteLedgerProjectionRepository(
        connection=reopened_connection,
    )
    try:
        entries = reopened_projection_repository.get_posted_entries(_scope())
        assert tuple(entry.id.value for entry in entries) == ("JE-REOPEN",)
    finally:
        reopened_manager.close()
