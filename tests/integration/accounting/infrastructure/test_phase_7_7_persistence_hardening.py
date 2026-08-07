"""Phase 7.7 integration coverage for persistence hardening goals."""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from educonnect_engine.accounting.application.create_journal_entry import (
    CreateJournalEntryCommand,
    CreateJournalEntryHandler,
)
from educonnect_engine.accounting.application.delete_draft_journal_entry import (
    ConcurrencyConflictError,
    DeleteDraftJournalEntryCommand,
    DeleteDraftJournalEntryHandler,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)
from educonnect_engine.accounting.infrastructure.sqlite.repositories import (
    SQLiteJournalEntryRepository,
)
from educonnect_engine.accounting.infrastructure.sqlite.unit_of_work import SQLiteUnitOfWork
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


def _line(side: DebitCreditSide, amount: str, account: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="phase-7.7",
    )


def test_phase_7_7_end_to_end_create_then_delete_draft_with_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "phase-7-7-e2e.db"
    _bootstrap_v2(db_path)

    config = DatabaseConfig(path=str(db_path))
    create_handler = CreateJournalEntryHandler(
        uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
    )
    delete_handler = DeleteDraftJournalEntryHandler(
        uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
    )

    entry_id = JournalEntryId(value="JE-2026-7-7-E2E")
    result = create_handler.execute(
        CreateJournalEntryCommand(
            journal_entry_id=entry_id,
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-7-7"),
            posting_date=date(2026, 1, 16),
            lines=(
                _line(DebitCreditSide.DEBIT, "12.00", "1000"),
                _line(DebitCreditSide.CREDIT, "12.00", "3000"),
            ),
        ),
    )
    assert result.journal_entry_id == entry_id
    assert result.version == 0

    manager = ConnectionFactory.create(config)
    connection = manager.open()
    try:
        repository = SQLiteJournalEntryRepository(connection=connection)
        loaded = repository.get_by_id(entry_id)
        assert loaded is not None
        assert loaded.id == entry_id
    finally:
        manager.close()

    delete_result = delete_handler.execute(
        DeleteDraftJournalEntryCommand(journal_entry_id=entry_id, expected_version=0),
    )
    assert delete_result.deleted is True

    reopened_manager = ConnectionFactory.create(config)
    reopened_connection = reopened_manager.open()
    try:
        reopened_repository = SQLiteJournalEntryRepository(connection=reopened_connection)
        missing = reopened_repository.get_by_id(entry_id)
        assert missing is None

        line_count = reopened_connection.execute(
            "SELECT COUNT(*) FROM journal_entry_lines WHERE entry_id = ?",
            (entry_id.value,),
        ).fetchone()
        assert line_count is not None
        assert int(line_count[0]) == 0
    finally:
        reopened_manager.close()


def test_phase_7_7_delete_draft_version_conflict_rolls_back(tmp_path: Path) -> None:
    db_path = tmp_path / "phase-7-7-version-conflict.db"
    _bootstrap_v2(db_path)

    config = DatabaseConfig(path=str(db_path))
    create_handler = CreateJournalEntryHandler(
        uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
    )
    delete_handler = DeleteDraftJournalEntryHandler(
        uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
    )

    entry_id = JournalEntryId(value="JE-2026-7-7-CONFLICT")
    create_handler.execute(
        CreateJournalEntryCommand(
            journal_entry_id=entry_id,
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-7-7-CONFLICT"),
            posting_date=date(2026, 1, 16),
            lines=(
                _line(DebitCreditSide.DEBIT, "50.00", "1000"),
                _line(DebitCreditSide.CREDIT, "50.00", "3000"),
            ),
        ),
    )

    with pytest.raises(ConcurrencyConflictError, match="version mismatch"):
        delete_handler.execute(
            DeleteDraftJournalEntryCommand(journal_entry_id=entry_id, expected_version=99),
        )

    manager = ConnectionFactory.create(config)
    connection = manager.open()
    try:
        repository = SQLiteJournalEntryRepository(connection=connection)
        loaded = repository.get_by_id(entry_id)
        assert loaded is not None
        assert loaded.version == 0
    finally:
        manager.close()


def test_phase_7_7_foreign_key_constraint_is_enforced(tmp_path: Path) -> None:
    db_path = tmp_path / "phase-7-7-fk.db"
    _bootstrap_v2(db_path)

    manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    connection = manager.open()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO journal_entry_lines(
                    entry_id, position, account_number, side, amount, currency, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("JE-MISSING", 0, "1000", "debit", "10.00", "CHF", "missing header"),
            )
    finally:
        manager.close()


def test_phase_7_7_architecture_forbids_sqlite_imports_in_domain_and_application() -> None:
    root = Path(__file__).resolve().parents[4]
    package_root = root / "src" / "educonnect_engine" / "accounting"

    forbidden_tokens = ("import sqlite3", "from sqlite3", "infrastructure.sqlite")

    for layer in ("domain", "application"):
        layer_root = package_root / layer
        for file_path in layer_root.rglob("*.py"):
            source = file_path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in source, f"forbidden token {token!r} in {file_path}"
