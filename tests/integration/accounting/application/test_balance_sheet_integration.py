"""Integration tests for Balance Sheet through the existing projection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from educonnect_engine.accounting.application.balance_sheet import (
    BalanceSheetCommand,
    GenerateBalanceSheet,
)
from educonnect_engine.accounting.application.ledger_projection import LedgerProjectionHandler
from educonnect_engine.accounting.application.trial_balance import TrialBalanceHandler
from educonnect_engine.accounting.domain.account_classification import AccountClassification
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


@dataclass(frozen=True, slots=True)
class _Classifier:
    def classify(self, account_number: AccountNumber) -> AccountClassification:
        return {
            "1000": AccountClassification.ASSET,
            "2000": AccountClassification.LIABILITY,
            "3000": AccountClassification.EQUITY,
        }[account_number.value]


def _line(account: str, side: DebitCreditSide, amount: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
    )


def test_generate_balance_sheet_from_sqlite_projection_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "balance-sheet-use-case.db"
    config = DatabaseConfig(path=str(db_path))
    SQLiteSchemaBootstrap(
        connection_factory=ConnectionFactory(),
        config=config,
        target_version=2,
    ).bootstrap()

    manager = ConnectionFactory.create(config)
    connection = manager.open()
    try:
        repository = SQLiteJournalEntryRepository(connection=connection)
        entry = JournalEntry.from_recorded(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            lines=(
                _line("1000", DebitCreditSide.DEBIT, "100.00"),
                _line("2000", DebitCreditSide.CREDIT, "70.00"),
                _line("3000", DebitCreditSide.CREDIT, "30.00"),
            ),
        ).post(posted_at=datetime(2026, 1, 31, 8, 0, tzinfo=UTC))
        repository.add(entry)
    finally:
        manager.close()

    trial_balance_handler = TrialBalanceHandler(
        ledger_projection_handler=LedgerProjectionHandler(
            uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
        ),
    )
    use_case = GenerateBalanceSheet(
        trial_balance_handler=trial_balance_handler,
        classifier=_Classifier(),
    )

    statements = use_case.execute(
        BalanceSheetCommand(
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            currency=Currency(code="CHF"),
        ),
    )

    assert statements.balance_sheet is not None
    assert statements.balance_sheet.assets_total().amount == Decimal("100.00")
    assert statements.balance_sheet.liabilities_total().amount == Decimal("70.00")
    assert statements.balance_sheet.equity_total().amount == Decimal("30.00")
    assert statements.balance_sheet.is_balanced() is True