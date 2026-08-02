"""Financial statements assembly object."""

from dataclasses import dataclass

from .balance_sheet import BalanceSheet
from .income_statement import IncomeStatement


class FinancialStatementsScopeMismatchError(Exception):
    """Raised when assembled statements do not share the same scope."""


class FinancialStatementsCurrencyMismatchError(Exception):
    """Raised when assembled statements do not share a consistent currency."""


class FinancialStatementsNetResultMismatchError(Exception):
    """Raised when income statement result differs from balance sheet period result."""


@dataclass(frozen=True, slots=True)
class FinancialStatements:
    """Immutable assembly of validated balance sheet and income statement."""

    balance_sheet: BalanceSheet
    income_statement: IncomeStatement

    def __post_init__(self) -> None:
        if self.balance_sheet.scope != self.income_statement.scope:
            raise FinancialStatementsScopeMismatchError(
                "balance sheet and income statement scopes must be identical",
            )

        scope_currency = self.income_statement.scope.currency
        if self.balance_sheet.current_period_result.currency != scope_currency:
            raise FinancialStatementsCurrencyMismatchError(
                "current period result currency must match shared statement scope currency",
            )
        if self.income_statement.net_result_amount().currency != scope_currency:
            raise FinancialStatementsCurrencyMismatchError(
                "income statement net result currency must match shared statement scope currency",
            )

        if (
            self.income_statement.net_result_side()
            is not self.balance_sheet.current_period_result.result_side
        ):
            raise FinancialStatementsNetResultMismatchError(
                (
                    "income statement net result side must match "
                    "balance sheet current period result side"
                ),
            )
        if (
            self.income_statement.net_result_amount()
            != self.balance_sheet.current_period_result.result_amount
        ):
            raise FinancialStatementsNetResultMismatchError(
                (
                    "income statement net result amount must match "
                    "balance sheet current period result amount"
                ),
            )
