"""Unit tests for IncomeStatementProjectionService."""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.financial_statement_account_classifier import (
    FinancialStatementAccountClassifier,
)
from educonnect_engine.accounting.domain.income_statement_projection_service import (
    IncomeStatementProjectionService,
    UnclassifiedIncomeStatementAccountError,
)
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.trial_balance import TrialBalance
from educonnect_engine.accounting.domain.trial_balance_line import TrialBalanceLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _scope() -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency=Currency(code="CHF"))


def _tb_line(account: str, debit: str, credit: str) -> TrialBalanceLine:
    return TrialBalanceLine(
        account_number=AccountNumber(value=account),
        currency=Currency(code="CHF"),
        debit_movement=_money(debit),
        credit_movement=_money(credit),
    )


@dataclass(frozen=True, slots=True)
class _Classifier(FinancialStatementAccountClassifier):
    mapping: dict[AccountNumber, AccountClassification]

    def classify(self, account_number: AccountNumber) -> AccountClassification:
        return self.mapping[account_number]


@dataclass(frozen=True, slots=True)
class _BrokenClassifier(FinancialStatementAccountClassifier):
    def classify(self, account_number: AccountNumber) -> AccountClassification:
        _ = account_number
        return "other"  # type: ignore[return-value]


def test_projection_income_statement_before_closing_profit() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "30.00", "0"),
            _tb_line("2000", "0", "30.00"),
            _tb_line("3000", "30.00", "0"),
            _tb_line("4000", "0", "50.00"),
            _tb_line("5000", "20.00", "0"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="4000"): AccountClassification.REVENUE,
            AccountNumber(value="5000"): AccountClassification.EXPENSE,
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
            AccountNumber(value="3000"): AccountClassification.EQUITY,
        },
    )

    statement = IncomeStatementProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert tuple(line.account_number.value for line in statement.revenues.lines) == ("4000",)
    assert tuple(line.account_number.value for line in statement.expenses.lines) == ("5000",)
    assert statement.revenue_total() == _money("50.00")
    assert statement.expense_total() == _money("20.00")
    assert statement.net_result_side() is DebitCreditSide.CREDIT
    assert statement.net_result_amount() == _money("30.00")


def test_projection_income_statement_handles_abnormal_sides() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "10.00", "0"),
            _tb_line("2000", "0", "10.00"),
            _tb_line("3000", "0", "10.00"),
            _tb_line("4000", "15.00", "0"),
            _tb_line("5000", "0", "5.00"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="4000"): AccountClassification.REVENUE,
            AccountNumber(value="5000"): AccountClassification.EXPENSE,
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
            AccountNumber(value="3000"): AccountClassification.EQUITY,
        },
    )

    statement = IncomeStatementProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert statement.revenue_total() == _money("15.00")
    assert statement.expense_total() == _money("5.00")
    assert statement.net_result_side() is DebitCreditSide.DEBIT
    assert statement.net_result_amount() == _money("10.00")


def test_projection_excludes_non_income_statement_classifications() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "10.00", "0"),
            _tb_line("2000", "0", "10.00"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
        },
    )

    statement = IncomeStatementProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert statement.revenues.lines == ()
    assert statement.expenses.lines == ()
    assert statement.net_result_side() is None
    assert statement.net_result_amount() == _money("0")


def test_projection_rejects_unclassified_account() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(_tb_line("1000", "10.00", "10.00"),),
    )

    with pytest.raises(UnclassifiedIncomeStatementAccountError):
        IncomeStatementProjectionService().project(
            trial_balance=trial_balance,
            classifier=_BrokenClassifier(),
        )


def test_projection_is_deterministic_and_does_not_mutate_trial_balance() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "5.00", "0"),
            _tb_line("2000", "0", "5.00"),
            _tb_line("3000", "5.00", "0"),
            _tb_line("4000", "0", "10.00"),
            _tb_line("4010", "0", "5.00"),
            _tb_line("5000", "7.00", "0"),
            _tb_line("5010", "3.00", "0"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="4000"): AccountClassification.REVENUE,
            AccountNumber(value="4010"): AccountClassification.REVENUE,
            AccountNumber(value="5000"): AccountClassification.EXPENSE,
            AccountNumber(value="5010"): AccountClassification.EXPENSE,
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
            AccountNumber(value="3000"): AccountClassification.EQUITY,
        },
    )
    before = trial_balance

    statement_a = IncomeStatementProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )
    statement_b = IncomeStatementProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert statement_a == statement_b
    assert trial_balance == before
    assert tuple(line.account_number.value for line in statement_a.revenues.lines) == (
        "4000",
        "4010",
    )
    assert tuple(line.account_number.value for line in statement_a.expenses.lines) == (
        "5000",
        "5010",
    )
