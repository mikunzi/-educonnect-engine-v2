"""Income statement projection service from trial balance."""

from dataclasses import dataclass

from .account_classification import AccountClassification
from .financial_statement_account_classifier import FinancialStatementAccountClassifier
from .income_statement import IncomeStatement
from .income_statement_line import IncomeStatementLine
from .income_statement_section import IncomeStatementSection
from .trial_balance import TrialBalance
from .trial_balance_line import TrialBalanceLine


class UnclassifiedIncomeStatementAccountError(Exception):
    """Raised when account classifier returns unknown classification."""


@dataclass(frozen=True, slots=True)
class IncomeStatementProjectionService:
    """Project a deterministic income statement from trial balance only."""

    def project(
        self,
        *,
        trial_balance: TrialBalance,
        classifier: FinancialStatementAccountClassifier,
    ) -> IncomeStatement:
        revenue_lines: list[IncomeStatementLine] = []
        expense_lines: list[IncomeStatementLine] = []

        for line in trial_balance.lines:
            classification = classifier.classify(line.account_number)
            if classification not in set(AccountClassification):
                raise UnclassifiedIncomeStatementAccountError(
                    "classifier returned unknown account classification",
                )

            if classification is AccountClassification.REVENUE:
                revenue_lines.append(
                    self._to_income_statement_line(classification=classification, trial_line=line),
                )
                continue
            if classification is AccountClassification.EXPENSE:
                expense_lines.append(
                    self._to_income_statement_line(classification=classification, trial_line=line),
                )

        currency = trial_balance.scope.currency
        revenues = IncomeStatementSection(
            classification=AccountClassification.REVENUE,
            currency=currency,
            lines=tuple(sorted(revenue_lines, key=lambda item: item.account_number.value)),
        )
        expenses = IncomeStatementSection(
            classification=AccountClassification.EXPENSE,
            currency=currency,
            lines=tuple(sorted(expense_lines, key=lambda item: item.account_number.value)),
        )

        return IncomeStatement(
            scope=trial_balance.scope,
            revenues=revenues,
            expenses=expenses,
        )

    def _to_income_statement_line(
        self,
        *,
        classification: AccountClassification,
        trial_line: TrialBalanceLine,
    ) -> IncomeStatementLine:
        return IncomeStatementLine(
            account_number=trial_line.account_number,
            classification=classification,
            currency=trial_line.currency,
            balance_side=trial_line.balance_side,
            balance_amount=trial_line.balance_amount,
        )
