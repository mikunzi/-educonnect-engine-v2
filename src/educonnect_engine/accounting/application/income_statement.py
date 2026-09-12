"""Income Statement application use case."""

from __future__ import annotations

from dataclasses import dataclass, field

from educonnect_engine.accounting.application.balance_sheet import TrialBalanceExecutor
from educonnect_engine.accounting.application.financial_statements import FinancialStatements
from educonnect_engine.accounting.application.trial_balance import TrialBalanceCommand
from educonnect_engine.accounting.domain.financial_statement_account_classifier import (
    FinancialStatementAccountClassifier,
)
from educonnect_engine.accounting.domain.income_statement_projection_service import (
    IncomeStatementProjectionService,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


@dataclass(frozen=True, slots=True)
class IncomeStatementCommand:
    """Input payload for generating one income statement."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    currency: Currency


@dataclass(frozen=True, slots=True)
class GenerateIncomeStatement:
    """Project an income statement from the existing Trial Balance use case."""

    trial_balance_handler: TrialBalanceExecutor
    classifier: FinancialStatementAccountClassifier
    projection_service: IncomeStatementProjectionService = field(
        default_factory=IncomeStatementProjectionService,
    )

    def execute(self, command: IncomeStatementCommand) -> FinancialStatements:
        trial_balance_result = self.trial_balance_handler.execute(
            TrialBalanceCommand(
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
                currency=command.currency,
            ),
        )
        income_statement = self.projection_service.project(
            trial_balance=trial_balance_result.trial_balance,
            classifier=self.classifier,
        )
        return FinancialStatements(income_statement=income_statement)