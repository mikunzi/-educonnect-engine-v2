"""Unit tests for GenerateIncomeStatement use case."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from decimal import Decimal

import pytest

import educonnect_engine.accounting.application.income_statement as income_statement_module
from educonnect_engine.accounting.application.financial_statements import (
    FinancialStatements,
    FinancialStatementsUseCase,
)
from educonnect_engine.accounting.application.income_statement import (
    GenerateIncomeStatement,
    IncomeStatementCommand,
)
from educonnect_engine.accounting.application.trial_balance import (
    TrialBalanceCommand,
    TrialBalanceResult,
)
from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet_projection_service import (
    BalanceSheetProjectionService,
)
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.income_statement_projection_service import (
    UnclassifiedIncomeStatementAccountError,
)
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.trial_balance import (
    TrialBalance,
    TrialBalanceCurrencyMismatchError,
)
from educonnect_engine.accounting.domain.trial_balance_line import TrialBalanceLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _TrialBalanceHandler:
    result: TrialBalanceResult
    calls: list[TrialBalanceCommand]

    def execute(self, command: TrialBalanceCommand) -> TrialBalanceResult:
        self.calls.append(command)
        return self.result


@dataclass(frozen=True, slots=True)
class _FailingTrialBalanceHandler:
    error: Exception

    def execute(self, command: TrialBalanceCommand) -> TrialBalanceResult:
        _ = command
        raise self.error


@dataclass(frozen=True, slots=True)
class _Classifier:
    mapping: dict[AccountNumber, AccountClassification]

    def classify(self, account_number: AccountNumber) -> AccountClassification:
        return self.mapping[account_number]


@dataclass(frozen=True, slots=True)
class _BrokenClassifier:
    def classify(self, account_number: AccountNumber) -> AccountClassification:
        _ = account_number
        return "unknown"  # type: ignore[return-value]


def _scope(currency: str = "CHF") -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code=currency),
    )


def _money(amount: str, currency: str = "CHF") -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code=currency))


def _line(account: str, debit: str, credit: str) -> TrialBalanceLine:
    return TrialBalanceLine(
        account_number=AccountNumber(value=account),
        currency=Currency(code="CHF"),
        debit_movement=_money(debit),
        credit_movement=_money(credit),
    )


def _result(trial_balance: TrialBalance) -> TrialBalanceResult:
    return TrialBalanceResult(
        scope=trial_balance.scope,
        trial_balance=trial_balance,
        journal_entry_count=1,
        ledger_line_count=len(trial_balance.lines),
        trial_balance_line_count=len(trial_balance.lines),
    )


def _command() -> IncomeStatementCommand:
    return IncomeStatementCommand(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _classifications(**mapping: AccountClassification) -> _Classifier:
    return _Classifier(
        mapping={
            AccountNumber(value=account_number): classification
            for account_number, classification in mapping.items()
        },
    )


def test_generate_empty_income_statement() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    handler = _TrialBalanceHandler(result=_result(trial_balance), calls=[])
    use_case = GenerateIncomeStatement(
        trial_balance_handler=handler,
        classifier=_Classifier(mapping={}),
    )

    statements = use_case.execute(_command())

    assert statements.income_statement is not None
    assert statements.income_statement.revenues.lines == ()
    assert statements.income_statement.expenses.lines == ()
    assert statements.income_statement.net_result_side() is None
    assert statements.income_statement.net_result_amount() == _money("0")
    assert statements.balance_sheet is None
    assert handler.calls == [
        TrialBalanceCommand(
            legal_entity_id=_command().legal_entity_id,
            fiscal_year=_command().fiscal_year,
            currency=_command().currency,
        ),
    ]


def test_generate_income_statement_projects_revenues_expenses_profit_and_order() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _line("1000", "70.0000", "0"),
            _line("2000", "0", "20.0000"),
            _line("4000", "0", "50.1234"),
            _line("4010", "0", "49.8766"),
            _line("5000", "20.0000", "0"),
            _line("5010", "30.0000", "0"),
        ),
    )
    use_case = GenerateIncomeStatement(
        trial_balance_handler=_TrialBalanceHandler(result=_result(trial_balance), calls=[]),
        classifier=_classifications(
            **{
                "1000": AccountClassification.ASSET,
                "2000": AccountClassification.LIABILITY,
                "4000": AccountClassification.REVENUE,
                "4010": AccountClassification.REVENUE,
                "5000": AccountClassification.EXPENSE,
                "5010": AccountClassification.EXPENSE,
            },
        ),
    )

    statements = use_case.execute(_command())

    assert statements.income_statement is not None
    income_statement = statements.income_statement
    assert tuple(line.account_number.value for line in income_statement.revenues.lines) == (
        "4000",
        "4010",
    )
    assert tuple(line.account_number.value for line in income_statement.expenses.lines) == (
        "5000",
        "5010",
    )
    assert income_statement.revenue_total() == _money("100.0000")
    assert income_statement.expense_total() == _money("50.0000")
    assert income_statement.net_result_side() is DebitCreditSide.CREDIT
    assert income_statement.net_result_amount() == _money("50.0000")


def test_generate_income_statement_projects_loss_and_abnormal_sides() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _line("1000", "10.00", "0"),
            _line("2000", "0", "10.00"),
            _line("3000", "0", "10.00"),
            _line("4000", "15.00", "0"),
            _line("5000", "0", "5.00"),
        ),
    )
    use_case = GenerateIncomeStatement(
        trial_balance_handler=_TrialBalanceHandler(result=_result(trial_balance), calls=[]),
        classifier=_classifications(
            **{
                "1000": AccountClassification.ASSET,
                "2000": AccountClassification.LIABILITY,
                "3000": AccountClassification.EQUITY,
                "4000": AccountClassification.REVENUE,
                "5000": AccountClassification.EXPENSE,
            },
        ),
    )

    statements = use_case.execute(_command())

    assert statements.income_statement is not None
    assert statements.income_statement.revenue_total() == _money("15.00")
    assert statements.income_statement.expense_total() == _money("5.00")
    assert statements.income_statement.net_result_side() is DebitCreditSide.DEBIT
    assert statements.income_statement.net_result_amount() == _money("10.00")


def test_generate_income_statement_propagates_classifier_error() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(_line("1000", "10.00", "10.00"),),
    )
    use_case = GenerateIncomeStatement(
        trial_balance_handler=_TrialBalanceHandler(result=_result(trial_balance), calls=[]),
        classifier=_BrokenClassifier(),
    )

    with pytest.raises(UnclassifiedIncomeStatementAccountError):
        use_case.execute(_command())


def test_generate_income_statement_propagates_trial_balance_error() -> None:
    error = TrialBalanceCurrencyMismatchError("invalid trial balance currency")
    use_case = GenerateIncomeStatement(
        trial_balance_handler=_FailingTrialBalanceHandler(error=error),
        classifier=_Classifier(mapping={}),
    )

    with pytest.raises(TrialBalanceCurrencyMismatchError) as raised:
        use_case.execute(_command())

    assert raised.value is error


def test_financial_statements_api_remains_backward_compatible() -> None:
    statements = FinancialStatementsUseCase().execute()

    assert statements.balance_sheet is None
    assert statements.income_statement is None


def test_financial_statements_preserves_existing_balance_sheet_field() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    balance_sheet = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=_Classifier(mapping={}),
    )

    statements = FinancialStatements(balance_sheet=balance_sheet)

    assert statements.balance_sheet is balance_sheet
    assert statements.income_statement is None


def test_income_statement_application_has_no_infrastructure_dependency() -> None:
    source = inspect.getsource(income_statement_module)
    forbidden_terms = ("sqlite3", "infrastructure", "SELECT ", "repository")

    assert all(term not in source for term in forbidden_terms)
