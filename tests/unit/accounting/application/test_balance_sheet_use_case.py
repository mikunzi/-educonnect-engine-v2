"""Unit tests for GenerateBalanceSheet use case."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from decimal import Decimal

import pytest

import educonnect_engine.accounting.application.balance_sheet as balance_sheet_module
from educonnect_engine.accounting.application.balance_sheet import (
    BalanceSheetCommand,
    GenerateBalanceSheet,
)
from educonnect_engine.accounting.application.financial_statements import (
    FinancialStatementsUseCase,
)
from educonnect_engine.accounting.application.trial_balance import (
    TrialBalanceCommand,
    TrialBalanceResult,
)
from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet import UnbalancedBalanceSheetError
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
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
class _Classifier:
    mapping: dict[AccountNumber, AccountClassification]

    def classify(self, account_number: AccountNumber) -> AccountClassification:
        return self.mapping[account_number]


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


def _command() -> BalanceSheetCommand:
    return BalanceSheetCommand(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def test_generate_empty_balance_sheet() -> None:
    trial_balance = TrialBalance(scope=_scope(), lines=())
    trial_balance_handler = _TrialBalanceHandler(result=_result(trial_balance), calls=[])
    use_case = GenerateBalanceSheet(
        trial_balance_handler=trial_balance_handler,
        classifier=_Classifier(mapping={}),
    )

    statements = use_case.execute(_command())

    assert statements.balance_sheet is not None
    assert statements.balance_sheet.assets.lines == ()
    assert statements.balance_sheet.liabilities.lines == ()
    assert statements.balance_sheet.equity.lines == ()
    assert statements.balance_sheet.assets_total() == _money("0")
    assert statements.balance_sheet.right_side_total() == _money("0")
    assert statements.balance_sheet.is_balanced() is True
    assert trial_balance_handler.calls == [
        TrialBalanceCommand(
            legal_entity_id=_command().legal_entity_id,
            fiscal_year=_command().fiscal_year,
            currency=_command().currency,
        ),
    ]


def test_generate_balance_sheet_classifies_totals_and_orders_accounts() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _line("1000", "100.1234", "0"),
            _line("1010", "49.8766", "0"),
            _line("2000", "0", "70.1111"),
            _line("2010", "0", "19.8889"),
            _line("3000", "0", "30.0000"),
            _line("4000", "0", "50.0000"),
            _line("5000", "20.0000", "0"),
        ),
    )
    classifications = {
        "1000": AccountClassification.ASSET,
        "1010": AccountClassification.ASSET,
        "2000": AccountClassification.LIABILITY,
        "2010": AccountClassification.LIABILITY,
        "3000": AccountClassification.EQUITY,
        "4000": AccountClassification.REVENUE,
        "5000": AccountClassification.EXPENSE,
    }
    use_case = GenerateBalanceSheet(
        trial_balance_handler=_TrialBalanceHandler(result=_result(trial_balance), calls=[]),
        classifier=_Classifier(
            mapping={
                AccountNumber(value=number): classification
                for number, classification in classifications.items()
            },
        ),
    )

    statements = use_case.execute(_command())

    assert statements.balance_sheet is not None
    balance_sheet = statements.balance_sheet
    assert tuple(line.account_number.value for line in balance_sheet.assets.lines) == (
        "1000",
        "1010",
    )
    assert tuple(line.account_number.value for line in balance_sheet.liabilities.lines) == (
        "2000",
        "2010",
    )
    assert tuple(line.account_number.value for line in balance_sheet.equity.lines) == ("3000",)
    statement_accounts = {
        line.account_number.value
        for section in (balance_sheet.assets, balance_sheet.liabilities, balance_sheet.equity)
        for line in section.lines
    }
    assert statement_accounts == {"1000", "1010", "2000", "2010", "3000"}
    assert balance_sheet.assets_total() == _money("150.0000")
    assert balance_sheet.liabilities_total() == _money("90.0000")
    assert balance_sheet.equity_total() == _money("30.0000")
    assert balance_sheet.current_period_result.result_amount == _money("30.0000")
    assert balance_sheet.is_balanced() is True
    assert balance_sheet.assets.lines[0].balance_side is DebitCreditSide.DEBIT
    assert balance_sheet.liabilities.lines[0].balance_side is DebitCreditSide.CREDIT


def test_generate_balance_sheet_rejects_unbalanced_classification() -> None:
    trial_balance = object.__new__(TrialBalance)
    object.__setattr__(trial_balance, "scope", _scope())
    object.__setattr__(
        trial_balance,
        "lines",
        (_line("1000", "10.00", "0"),),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1000"): AccountClassification.ASSET,
        },
    )
    use_case = GenerateBalanceSheet(
        trial_balance_handler=_TrialBalanceHandler(result=_result(trial_balance), calls=[]),
        classifier=classifier,
    )

    with pytest.raises(UnbalancedBalanceSheetError):
        use_case.execute(_command())


def test_trial_balance_rejects_multiple_currencies_before_balance_sheet() -> None:
    with pytest.raises(TrialBalanceCurrencyMismatchError):
        TrialBalance(
            scope=_scope(currency="CHF"),
            lines=(
                TrialBalanceLine(
                    account_number=AccountNumber(value="1000"),
                    currency=Currency(code="EUR"),
                    debit_movement=_money("10.00", currency="EUR"),
                    credit_movement=_money("10.00", currency="EUR"),
                ),
            ),
        )


def test_financial_statements_api_remains_backward_compatible() -> None:
    statements = FinancialStatementsUseCase().execute()

    assert statements.balance_sheet is None


def test_balance_sheet_application_has_no_infrastructure_dependency() -> None:
    source = inspect.getsource(balance_sheet_module)
    assert "sqlite3" not in source
    assert "infrastructure" not in source
