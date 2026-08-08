"""Unit tests for FinancialStatements use case."""

from educonnect_engine.accounting.application.financial_statements import (
    FinancialStatements,
    FinancialStatementsUseCase,
)


def test_execute_returns_financial_statements() -> None:
    use_case = FinancialStatementsUseCase()

    result = use_case.execute()

    assert isinstance(result, FinancialStatements)