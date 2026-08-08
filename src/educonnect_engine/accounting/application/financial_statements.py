"""Financial statements application API."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FinancialStatements:
    """Placeholder for future financial statement projections."""


@dataclass(frozen=True, slots=True)
class FinancialStatementsUseCase:
    """Application use case exposing the financial statements API."""

    def execute(self) -> FinancialStatements:
        return FinancialStatements()