"""Integration tests for LedgerProjection use case with SQLite adapters."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from educonnect_engine.accounting.application.ledger_projection import (
    LedgerProjectionCommand,
    LedgerProjectionHandler,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
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


def _line(account: str, side: DebitCreditSide, amount: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
    )


def _posted_entry(entry_id: str, posted_hour: int) -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value=f"REF-{entry_id}"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line("1000", DebitCreditSide.DEBIT, "10.00"),
            _line("2000", DebitCreditSide.CREDIT, "10.00"),
        ),
    ).post(posted_at=datetime(2026, 1, 31, posted_hour, 0, tzinfo=UTC))


def test_ledger_projection_projects_sqlite_posted_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger-projection-use-case.db"
    _bootstrap_v2(db_path)

    config = DatabaseConfig(path=str(db_path))
    manager = ConnectionFactory.create(config)
    connection = manager.open()
    try:
        journal_repository = SQLiteJournalEntryRepository(connection=connection)
        journal_repository.add(_posted_entry("JE-001", 8))
        journal_repository.add(_posted_entry("JE-002", 9))
    finally:
        manager.close()

    handler = LedgerProjectionHandler(
        uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
    )

    result = handler.execute(
        LedgerProjectionCommand(
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            currency=Currency(code="CHF"),
        ),
    )

    assert result.journal_entry_count == 2
    assert result.ledger_line_count == 4
    assert len(result.ledger.accounts) == 2
    assert result.ledger.total_debit().amount == Decimal("20.00")
    assert result.ledger.total_credit().amount == Decimal("20.00")
