"""Financial statements projection service."""

from dataclasses import dataclass

from .balance_sheet import BalanceSheet
from .financial_statements import FinancialStatements
from .income_statement import IncomeStatement


@dataclass(frozen=True, slots=True)
class FinancialStatementsProjectionService:
    """Assemble financial statements from validated statement projections only."""

    def project(
        self,
        *,
        balance_sheet: BalanceSheet,
        income_statement: IncomeStatement,
    ) -> FinancialStatements:
        return FinancialStatements(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )
