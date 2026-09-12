"""Unit tests for Financial Statements application use cases."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from decimal import Decimal

import pytest

import educonnect_engine.accounting.application.financial_statements as financial_statements_module
from educonnect_engine.accounting.application.financial_statements import (
    FinancialStatements,
    FinancialStatementsCommand,
    FinancialStatementsUseCase,
    GenerateFinancialStatements,
)
from educonnect_engine.accounting.application.trial_balance import (
    TrialBalanceCommand,
    TrialBalanceResult,
)
from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet import BalanceSheet
from educonnect_engine.accounting.domain.balance_sheet_projection_service import (
    BalanceSheetProjectionService,
)
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.financial_statement_account_classifier import (
    FinancialStatementAccountClassifier,
)
from educonnect_engine.accounting.domain.financial_statements import (
    FinancialStatements as DomainFinancialStatements,
)
from educonnect_engine.accounting.domain.financial_statements import (
    FinancialStatementsNetResultMismatchError,
)
from educonnect_engine.accounting.domain.financial_statements_projection_service import (
    FinancialStatementsProjectionService,
)
from educonnect_engine.accounting.domain.income_statement import IncomeStatement
from educonnect_engine.accounting.domain.income_statement_projection_service import (
    IncomeStatementProjectionService,
)
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.trial_balance_line import TrialBalanceLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


class _TrialBalanceFailureError(Exception):
    pass


class _BalanceSheetProjectionFailureError(Exception):
    pass


class _IncomeStatementProjectionFailureError(Exception):
    pass


@dataclass
class _TrialBalanceExecutor:
    result: TrialBalanceResult
    calls: list[TrialBalanceCommand]

    def execute(self, command: TrialBalanceCommand) -> TrialBalanceResult:
        self.calls.append(command)
        return self.result


@dataclass(frozen=True, slots=True)
class _FailingTrialBalanceExecutor:
    error: Exception

    def execute(self, command: TrialBalanceCommand) -> TrialBalanceResult:
        _ = command
        raise self.error


@dataclass(frozen=True, slots=True)
class _Classifier:
    mapping: dict[AccountNumber, AccountClassification]

    def classify(self, account_number: AccountNumber) -> AccountClassification:
        return self.mapping[account_number]


@dataclass
class _BalanceSheetProjectionSpy:
    trial_balances: list[TrialBalance]
    classifiers: list[FinancialStatementAccountClassifier]

    def project(
        self,
        *,
        trial_balance: TrialBalance,
        classifier: FinancialStatementAccountClassifier,
    ) -> BalanceSheet:
        self.trial_balances.append(trial_balance)
        self.classifiers.append(classifier)
        return BalanceSheetProjectionService().project(
            trial_balance=trial_balance,
            classifier=classifier,
        )


@dataclass
class _IncomeStatementProjectionSpy:
    trial_balances: list[TrialBalance]
    classifiers: list[FinancialStatementAccountClassifier]

    def project(
        self,
        *,
        trial_balance: TrialBalance,
        classifier: FinancialStatementAccountClassifier,
    ) -> IncomeStatement:
        self.trial_balances.append(trial_balance)
        self.classifiers.append(classifier)
        return IncomeStatementProjectionService().project(
            trial_balance=trial_balance,
            classifier=classifier,
        )


@dataclass
class _FinancialStatementsProjectionSpy:
    calls: list[tuple[BalanceSheet, IncomeStatement]]

    def project(
        self,
        *,
        balance_sheet: BalanceSheet,
        income_statement: IncomeStatement,
    ) -> DomainFinancialStatements:
        self.calls.append((balance_sheet, income_statement))
        return FinancialStatementsProjectionService().project(
            balance_sheet=balance_sheet,
            income_statement=income_statement,
        )


@dataclass(frozen=True, slots=True)
class _FailingProjectionService:
    error: Exception

    def project(self, **kwargs: object) -> object:
        _ = kwargs
        raise self.error


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code="CHF"))


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


def _command() -> FinancialStatementsCommand:
    return FinancialStatementsCommand(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _classifier(mapping: dict[str, AccountClassification]) -> _Classifier:
    return _Classifier(
        mapping={
            AccountNumber(value=account_number): classification
            for account_number, classification in mapping.items()
        },
    )


def _generate(
    trial_balance: TrialBalance,
    classifier: FinancialStatementAccountClassifier,
) -> tuple[
    FinancialStatements,
    _TrialBalanceExecutor,
    _BalanceSheetProjectionSpy,
    _IncomeStatementProjectionSpy,
    _FinancialStatementsProjectionSpy,
]:
    trial_balance_handler = _TrialBalanceExecutor(result=_result(trial_balance), calls=[])
    balance_sheet_service = _BalanceSheetProjectionSpy(trial_balances=[], classifiers=[])
    income_statement_service = _IncomeStatementProjectionSpy(trial_balances=[], classifiers=[])
    assembly_service = _FinancialStatementsProjectionSpy(calls=[])
    use_case = GenerateFinancialStatements(
        trial_balance_handler=trial_balance_handler,
        classifier=classifier,
        balance_sheet_projection_service=balance_sheet_service,
        income_statement_projection_service=income_statement_service,
        financial_statements_projection_service=assembly_service,
    )

    statements = use_case.execute(_command())

    return (
        statements,
        trial_balance_handler,
        balance_sheet_service,
        income_statement_service,
        assembly_service,
    )


def test_generate_financial_statements_orchestrates_one_trial_balance() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    classifier = _Classifier(mapping={})

    statements, handler, balance_service, income_service, assembly_service = _generate(
        trial_balance,
        classifier,
    )

    assert handler.calls == [
        TrialBalanceCommand(
            legal_entity_id=_command().legal_entity_id,
            fiscal_year=_command().fiscal_year,
            currency=_command().currency,
        ),
    ]
    assert balance_service.trial_balances == [trial_balance]
    assert income_service.trial_balances == [trial_balance]
    assert balance_service.trial_balances[0] is income_service.trial_balances[0]
    assert balance_service.classifiers == [classifier]
    assert income_service.classifiers == [classifier]
    assert balance_service.classifiers[0] is income_service.classifiers[0]
    assert len(assembly_service.calls) == 1
    assert statements.balance_sheet is assembly_service.calls[0][0]
    assert statements.income_statement is assembly_service.calls[0][1]


@pytest.mark.parametrize(
    ("lines", "mapping", "expected_side", "expected_amount"),
    [
        ((), {}, None, "0"),
        (
            (
                _line("1000", "30.00", "0"),
                _line("4000", "0", "50.00"),
                _line("5000", "20.00", "0"),
            ),
            {
                "1000": AccountClassification.ASSET,
                "4000": AccountClassification.REVENUE,
                "5000": AccountClassification.EXPENSE,
            },
            DebitCreditSide.CREDIT,
            "30.00",
        ),
        (
            (
                _line("2000", "0", "5.00"),
                _line("4000", "0", "15.00"),
                _line("5000", "20.00", "0"),
            ),
            {
                "2000": AccountClassification.LIABILITY,
                "4000": AccountClassification.REVENUE,
                "5000": AccountClassification.EXPENSE,
            },
            DebitCreditSide.DEBIT,
            "5.00",
        ),
        (
            (
                _line("1000", "10.00", "0"),
                _line("2000", "0", "10.00"),
                _line("4000", "0", "5.00"),
                _line("5000", "5.00", "0"),
            ),
            {
                "1000": AccountClassification.ASSET,
                "2000": AccountClassification.LIABILITY,
                "4000": AccountClassification.REVENUE,
                "5000": AccountClassification.EXPENSE,
            },
            None,
            "0",
        ),
    ],
    ids=("empty", "profit", "loss", "zero-result"),
)
def test_generate_financial_statements_returns_validated_components(
    lines: tuple[TrialBalanceLine, ...],
    mapping: dict[str, AccountClassification],
    expected_side: DebitCreditSide | None,
    expected_amount: str,
) -> None:
    statements, _, _, _, assembly_service = _generate(
        TrialBalance(scope=_scope(), lines=lines),
        _classifier(mapping),
    )

    assert statements.balance_sheet is not None
    assert statements.income_statement is not None
    assert len(assembly_service.calls) == 1
    assert statements.balance_sheet.current_period_result.result_side is expected_side
    assert statements.balance_sheet.current_period_result.result_amount == _money(expected_amount)
    assert statements.income_statement.net_result_side() is expected_side
    assert statements.income_statement.net_result_amount() == _money(expected_amount)


def test_generate_financial_statements_propagates_trial_balance_error() -> None:
    error = _TrialBalanceFailureError("trial balance failed")
    use_case = GenerateFinancialStatements(
        trial_balance_handler=_FailingTrialBalanceExecutor(error=error),
        classifier=_Classifier(mapping={}),
    )

    with pytest.raises(_TrialBalanceFailureError) as raised:
        use_case.execute(_command())

    assert raised.value is error


def test_generate_financial_statements_propagates_balance_sheet_error() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    error = _BalanceSheetProjectionFailureError("balance sheet failed")
    use_case = GenerateFinancialStatements(
        trial_balance_handler=_TrialBalanceExecutor(result=_result(trial_balance), calls=[]),
        classifier=_Classifier(mapping={}),
        balance_sheet_projection_service=_FailingProjectionService(error=error),
    )

    with pytest.raises(_BalanceSheetProjectionFailureError) as raised:
        use_case.execute(_command())

    assert raised.value is error


def test_generate_financial_statements_propagates_income_statement_error() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    error = _IncomeStatementProjectionFailureError("income statement failed")
    use_case = GenerateFinancialStatements(
        trial_balance_handler=_TrialBalanceExecutor(result=_result(trial_balance), calls=[]),
        classifier=_Classifier(mapping={}),
        income_statement_projection_service=_FailingProjectionService(error=error),
    )

    with pytest.raises(_IncomeStatementProjectionFailureError) as raised:
        use_case.execute(_command())

    assert raised.value is error


def test_generate_financial_statements_propagates_domain_assembly_error() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    error = FinancialStatementsNetResultMismatchError("statements mismatch")
    use_case = GenerateFinancialStatements(
        trial_balance_handler=_TrialBalanceExecutor(result=_result(trial_balance), calls=[]),
        classifier=_Classifier(mapping={}),
        financial_statements_projection_service=_FailingProjectionService(error=error),
    )

    with pytest.raises(FinancialStatementsNetResultMismatchError) as raised:
        use_case.execute(_command())

    assert raised.value is error


def test_financial_statements_api_remains_backward_compatible() -> None:
    empty = FinancialStatementsUseCase().execute()
    trial_balance = TrialBalance(scope=_scope(), lines=())
    domain_statements = FinancialStatementsProjectionService().project(
        balance_sheet=BalanceSheetProjectionService().project(
            trial_balance=trial_balance,
            classifier=_Classifier(mapping={}),
        ),
        income_statement=IncomeStatementProjectionService().project(
            trial_balance=trial_balance,
            classifier=_Classifier(mapping={}),
        ),
    )

    balance_only = FinancialStatements(balance_sheet=domain_statements.balance_sheet)
    income_only = FinancialStatements(income_statement=domain_statements.income_statement)

    assert empty == FinancialStatements()
    assert balance_only.balance_sheet is domain_statements.balance_sheet
    assert balance_only.income_statement is None
    assert income_only.balance_sheet is None
    assert income_only.income_statement is domain_statements.income_statement


def test_financial_statements_application_has_no_infrastructure_dependency() -> None:
    source = inspect.getsource(financial_statements_module)
    forbidden_terms = ("sqlite3", "infrastructure", "SELECT ", "repository")

    assert all(term not in source for term in forbidden_terms)