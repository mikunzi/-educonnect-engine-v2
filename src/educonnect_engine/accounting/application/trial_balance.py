"""TrialBalance use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from educonnect_engine.accounting.application.ledger_projection import (
    LedgerProjectionCommand,
    LedgerProjectionResult,
)
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.trial_balance_projection_service import (
    TrialBalanceProjectionService,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class LedgerProjectionExecutor(Protocol):
    """Abstraction for executing ledger projection before trial balance projection."""

    def execute(self, command: LedgerProjectionCommand) -> LedgerProjectionResult:
        """Project ledger for one explicit scope."""


@dataclass(frozen=True, slots=True)
class TrialBalanceCommand:
    """Input payload for projecting one trial balance scope."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    currency: Currency


@dataclass(frozen=True, slots=True)
class TrialBalanceResult:
    """Typed output returned by TrialBalance."""

    scope: LedgerScope
    trial_balance: TrialBalance
    journal_entry_count: int
    ledger_line_count: int
    trial_balance_line_count: int


@dataclass(frozen=True, slots=True)
class TrialBalanceHandler:
    """Application service projecting trial balance from ledger projection."""

    ledger_projection_handler: LedgerProjectionExecutor
    projection_service: TrialBalanceProjectionService = field(
        default_factory=TrialBalanceProjectionService,
    )

    def execute(self, command: TrialBalanceCommand) -> TrialBalanceResult:
        ledger_result = self.ledger_projection_handler.execute(
            LedgerProjectionCommand(
                legal_entity_id=command.legal_entity_id,
                fiscal_year=command.fiscal_year,
                currency=command.currency,
            ),
        )
        trial_balance = self.projection_service.project(ledger=ledger_result.ledger)
        return TrialBalanceResult(
            scope=ledger_result.scope,
            trial_balance=trial_balance,
            journal_entry_count=ledger_result.journal_entry_count,
            ledger_line_count=ledger_result.ledger_line_count,
            trial_balance_line_count=len(trial_balance.lines),
        )
