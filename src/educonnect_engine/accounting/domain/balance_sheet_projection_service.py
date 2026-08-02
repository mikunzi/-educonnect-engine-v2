"""Balance sheet projection service from trial balance."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money

from .account_classification import AccountClassification
from .balance_sheet import BalanceSheet
from .balance_sheet_line import BalanceSheetLine
from .balance_sheet_section import BalanceSheetSection
from .current_period_result import CurrentPeriodResult
from .financial_statement_account_classifier import FinancialStatementAccountClassifier
from .trial_balance import TrialBalance
from .trial_balance_line import TrialBalanceLine


class UnclassifiedBalanceSheetAccountError(Exception):
    """Raised when account classifier returns unknown classification."""


@dataclass(frozen=True, slots=True)
class BalanceSheetProjectionService:
    """Project a deterministic balance sheet from trial balance only."""

    def project(
        self,
        *,
        trial_balance: TrialBalance,
        classifier: FinancialStatementAccountClassifier,
    ) -> BalanceSheet:
        asset_lines: list[BalanceSheetLine] = []
        liability_lines: list[BalanceSheetLine] = []
        equity_lines: list[BalanceSheetLine] = []

        revenue_total = Decimal("0")
        expense_total = Decimal("0")

        for line in trial_balance.lines:
            classification = classifier.classify(line.account_number)
            if classification not in set(AccountClassification):
                raise UnclassifiedBalanceSheetAccountError(
                    "classifier returned unknown account classification",
                )

            if classification is AccountClassification.ASSET:
                asset_lines.append(
                    self._to_balance_sheet_line(classification=classification, trial_line=line),
                )
                continue
            if classification is AccountClassification.LIABILITY:
                liability_lines.append(
                    self._to_balance_sheet_line(classification=classification, trial_line=line),
                )
                continue
            if classification is AccountClassification.EQUITY:
                equity_lines.append(
                    self._to_balance_sheet_line(classification=classification, trial_line=line),
                )
                continue
            if classification is AccountClassification.REVENUE:
                signed_revenue = line.credit_movement.amount - line.debit_movement.amount
                if signed_revenue >= 0:
                    revenue_total += signed_revenue
                else:
                    expense_total += -signed_revenue
                continue

            signed_expense = line.debit_movement.amount - line.credit_movement.amount
            if signed_expense >= 0:
                expense_total += signed_expense
            else:
                revenue_total += -signed_expense

        currency = trial_balance.scope.currency
        current_period_result = CurrentPeriodResult(
            currency=currency,
            revenue_total=_money(revenue_total, currency),
            expense_total=_money(expense_total, currency),
        )

        assets = BalanceSheetSection(
            classification=AccountClassification.ASSET,
            currency=currency,
            lines=tuple(sorted(asset_lines, key=lambda item: item.account_number.value)),
        )
        liabilities = BalanceSheetSection(
            classification=AccountClassification.LIABILITY,
            currency=currency,
            lines=tuple(sorted(liability_lines, key=lambda item: item.account_number.value)),
        )
        equity = BalanceSheetSection(
            classification=AccountClassification.EQUITY,
            currency=currency,
            lines=tuple(sorted(equity_lines, key=lambda item: item.account_number.value)),
        )

        return BalanceSheet(
            scope=trial_balance.scope,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            current_period_result=current_period_result,
        )

    def _to_balance_sheet_line(
        self,
        *,
        classification: AccountClassification,
        trial_line: TrialBalanceLine,
    ) -> BalanceSheetLine:
        return BalanceSheetLine(
            account_number=trial_line.account_number,
            classification=classification,
            currency=trial_line.currency,
            balance_side=trial_line.balance_side,
            balance_amount=trial_line.balance_amount,
        )


def _money(amount: Decimal, currency: Currency) -> Money:
    return Money(amount=amount, currency=currency)
