"""Balance Sheet application use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from educonnect_engine.accounting.application.financial_statements import FinancialStatements
from educonnect_engine.accounting.application.trial_balance import (
    TrialBalanceCommand,
    TrialBalanceResult,
)
from educonnect_engine.accounting.domain.balance_sheet_projection_service import (
    BalanceSheetProjectionService,
)
from educonnect_engine.accounting.domain.financial_statement_account_classifier import (
    FinancialStatementAccountClassifier,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class TrialBalanceExecutor(Protocol):
    """Execute the existing Trial Balance application use case."""

    def execute(self, command: TrialBalanceCommand) -> TrialBalanceResult:
        """Generate one trial balance for an explicit scope."""


@dataclass(frozen=True, slots=True)
class BalanceSheetCommand:
    """Input payload for generating one balance sheet."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    currency: Currency


@dataclass(frozen=True, slots=True)
class GenerateBalanceSheet:
    """Project a balance sheet from the existing Trial Balance use case."""

    trial_balance_handler: TrialBalanceExecutor
    classifier: FinancialStatementAccountClassifier
    projection_service: BalanceSheetProjectionService = field(
        default_factory=BalanceSheetProjectionService,
    )

    def execute(self, command: BalanceSheetCommand) -> FinancialStatements:
        trial_balance_result = self.trial_balance_handler.execute(
            TrialBalanceCommand(
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
                currency=command.currency,
            ),
        )
        balance_sheet = self.projection_service.project(
            trial_balance=trial_balance_result.trial_balance,
            classifier=self.classifier,
        )
        return FinancialStatements(balance_sheet=balance_sheet)