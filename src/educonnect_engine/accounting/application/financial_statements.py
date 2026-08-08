"""Financial statements application API."""

from dataclasses import dataclass

from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet


@dataclass(frozen=True, slots=True)
class FinancialStatements:
    """Placeholder for future financial statement projections."""

    balance_sheet: BalanceSheet | None = None


@dataclass(frozen=True, slots=True)
class FinancialStatementsUseCase:
    """Application use case exposing the financial statements API."""

    def execute(self) -> FinancialStatements:
        return FinancialStatements()