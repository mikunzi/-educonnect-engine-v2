"""Unit tests for BalanceSheetProjectionService."""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.balance_sheet_projection_service import (
    BalanceSheetProjectionService,
    UnclassifiedBalanceSheetAccountError,
)
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.financial_statement_account_classifier import (
    FinancialStatementAccountClassifier,
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


def test_projection_before_closing_integrates_current_period_result() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "100.00", "0"),
            _tb_line("2000", "0", "70.00"),
            _tb_line("4000", "0", "50.00"),
            _tb_line("5000", "20.00", "0"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
            AccountNumber(value="4000"): AccountClassification.REVENUE,
            AccountNumber(value="5000"): AccountClassification.EXPENSE,
        },
    )

    balance_sheet = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert tuple(line.account_number.value for line in balance_sheet.assets.lines) == ("1000",)
    assert tuple(line.account_number.value for line in balance_sheet.liabilities.lines) == ("2000",)
    assert balance_sheet.equity.lines == ()
    assert balance_sheet.current_period_result.result_side is DebitCreditSide.CREDIT
    assert balance_sheet.current_period_result.result_amount == _money("30.00")
    assert balance_sheet.is_balanced() is True


def test_projection_after_closing_keeps_result_zero() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "100.00", "0"),
            _tb_line("2000", "0", "70.00"),
            _tb_line("3000", "0", "30.00"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
            AccountNumber(value="3000"): AccountClassification.EQUITY,
        },
    )

    balance_sheet = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert balance_sheet.current_period_result.result_side is None
    assert balance_sheet.current_period_result.result_amount == _money("0")
    assert balance_sheet.is_balanced() is True


def test_projection_rejects_unclassified_account() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(_tb_line("1000", "10.00", "10.00"),),
    )

    with pytest.raises(UnclassifiedBalanceSheetAccountError):
        BalanceSheetProjectionService().project(
            trial_balance=trial_balance,
            classifier=_BrokenClassifier(),
        )


def test_projection_does_not_mutate_trial_balance() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(_tb_line("1000", "10.00", "10.00"),),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1000"): AccountClassification.ASSET,
        },
    )
    before = trial_balance

    _ = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert trial_balance == before


def test_projection_handles_abnormal_revenue_and_expense_signs() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "60.00", "0"),
            _tb_line("2000", "0", "100.00"),
            _tb_line("4000", "50.00", "0"),
            _tb_line("5000", "0", "10.00"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
            AccountNumber(value="4000"): AccountClassification.REVENUE,
            AccountNumber(value="5000"): AccountClassification.EXPENSE,
        },
    )

    balance_sheet = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert balance_sheet.current_period_result.result_side is DebitCreditSide.DEBIT
    assert balance_sheet.current_period_result.result_amount == _money("40.00")
    assert balance_sheet.is_balanced() is True


def test_projection_sorts_section_lines_by_account_number() -> None:
    trial_balance = TrialBalance(
        scope=_scope(),
        lines=(
            _tb_line("1000", "60.00", "0"),
            _tb_line("1010", "40.00", "0"),
            _tb_line("2000", "0", "100.00"),
        ),
    )
    classifier = _Classifier(
        mapping={
            AccountNumber(value="1010"): AccountClassification.ASSET,
            AccountNumber(value="1000"): AccountClassification.ASSET,
            AccountNumber(value="2000"): AccountClassification.LIABILITY,
        },
    )

    balance_sheet = BalanceSheetProjectionService().project(
        trial_balance=trial_balance,
        classifier=classifier,
    )

    assert tuple(line.account_number.value for line in balance_sheet.assets.lines) == (
        "1000",
        "1010",
    )
