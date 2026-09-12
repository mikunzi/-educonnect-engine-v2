"""Financial statements application API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from educonnect_engine.accounting.application.trial_balance import TrialBalanceCommand
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_projection_service import (
    BalanceSheetProjectionService,
)
from educonnect_engine.accounting.domain.financial_statement_account_classifier import (
    FinancialStatementAccountClassifier,
)
from educonnect_engine.accounting.domain.financial_statements_projection_service import (
    FinancialStatementsProjectionService,
)
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_projection_service import (
    IncomeStatementProjectionService,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId

if TYPE_CHECKING:
    from educonnect_engine.accounting.application.balance_sheet import TrialBalanceExecutor


@dataclass(frozen=True, slots=True)
class FinancialStatements:
    """Placeholder for future financial statement projections."""

    balance_sheet: BalanceSheet | None = None
    income_statement: IncomeStatement | None = None


@dataclass(frozen=True, slots=True)
class FinancialStatementsUseCase:
    """Application use case exposing the financial statements API."""

    def execute(self) -> FinancialStatements:
        return FinancialStatements()


@dataclass(frozen=True, slots=True)
class FinancialStatementsCommand:
    """Input payload for generating complete financial statements."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    currency: Currency


@dataclass(frozen=True, slots=True)
class GenerateFinancialStatements:
    """Project and assemble financial statements from one trial balance."""

    trial_balance_handler: TrialBalanceExecutor
    classifier: FinancialStatementAccountClassifier
    balance_sheet_projection_service: BalanceSheetProjectionService = field(
        default_factory=BalanceSheetProjectionService,
    )
    income_statement_projection_service: IncomeStatementProjectionService = field(
        default_factory=IncomeStatementProjectionService,
    )
    financial_statements_projection_service: FinancialStatementsProjectionService = field(
        default_factory=FinancialStatementsProjectionService,
    )

    def execute(self, command: FinancialStatementsCommand) -> FinancialStatements:
        trial_balance_result = self.trial_balance_handler.execute(
            TrialBalanceCommand(
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
                currency=command.currency,
            ),
        )
        trial_balance = trial_balance_result.trial_balance
        balance_sheet = self.balance_sheet_projection_service.project(
            trial_balance=trial_balance,
            classifier=self.classifier,
        )
        income_statement = self.income_statement_projection_service.project(
            trial_balance=trial_balance,
            classifier=self.classifier,
        )
        validated = self.financial_statements_projection_service.project(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )
        return FinancialStatements(
            balance_sheet=validated.balance_sheet,
            income_statement=validated.income_statement,
        )