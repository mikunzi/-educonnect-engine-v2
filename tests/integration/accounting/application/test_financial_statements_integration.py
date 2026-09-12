"""Integration tests for Financial Statements through the projection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from educonnect_engine.accounting.application.financial_statements import (
    FinancialStatementsCommand,
    GenerateFinancialStatements,
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
            "4000": AccountClassification.REVENUE,
            "5000": AccountClassification.EXPENSE,
        }[account_number.value]


def _line(account: str, side: DebitCreditSide, amount: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="line",
    )


def test_generate_financial_statements_from_sqlite_projection_pipeline(tmp_path: Path) -> None:
    config = DatabaseConfig(path=str(tmp_path / "financial-statements-use-case.db"))
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
                _line("1000", DebitCreditSide.DEBIT, "130.1234"),
                _line("2000", DebitCreditSide.CREDIT, "70.0000"),
                _line("3000", DebitCreditSide.CREDIT, "30.0000"),
                _line("4000", DebitCreditSide.CREDIT, "50.1234"),
                _line("5000", DebitCreditSide.DEBIT, "20.0000"),
            ),
        ).post(posted_at=datetime(2026, 1, 31, 8, 0, tzinfo=UTC))
        repository.add(entry)
    finally:
        manager.close()

    use_case = GenerateFinancialStatements(
        trial_balance_handler=TrialBalanceHandler(
            ledger_projection_handler=LedgerProjectionHandler(
                uow=SQLiteUnitOfWork(connection_factory=ConnectionFactory(), config=config),
            ),
        ),
        classifier=_Classifier(),
    )

    statements = use_case.execute(
        FinancialStatementsCommand(
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            currency=Currency(code="CHF"),
        ),
    )

    assert statements.balance_sheet is not None
    assert statements.income_statement is not None
    assert statements.balance_sheet.assets_total().amount == Decimal("130.1234")
    assert statements.balance_sheet.liabilities_total().amount == Decimal("70.0000")
    assert statements.balance_sheet.equity_total().amount == Decimal("30.0000")
    assert statements.balance_sheet.is_balanced() is True
    assert statements.income_statement.revenue_total().amount == Decimal("50.1234")
    assert statements.income_statement.expense_total().amount == Decimal("20.0000")
    assert statements.income_statement.net_result_side() is DebitCreditSide.CREDIT
    assert statements.income_statement.net_result_amount().amount == Decimal("30.1234")
    assert (
        statements.balance_sheet.current_period_result.result_amount
        == statements.income_statement.net_result_amount()
    )