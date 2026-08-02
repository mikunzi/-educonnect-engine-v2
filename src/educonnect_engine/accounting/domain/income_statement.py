"""Income statement projection aggregate."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.money import Money

from .account_classification import AccountClassification
from .debit_credit_side import DebitCreditSide
from .income_statement_section import IncomeStatementSection
from .ledger_scope import LedgerScope


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    """Immutable income statement with derived totals."""

    scope: LedgerScope
    revenues: IncomeStatementSection
    expenses: IncomeStatementSection

    def __post_init__(self) -> None:
        if self.revenues.classification is not AccountClassification.REVENUE:
            raise ValueError("revenues section must use REVENUE classification")
        if self.expenses.classification is not AccountClassification.EXPENSE:
            raise ValueError("expenses section must use EXPENSE classification")

        for section in (self.revenues, self.expenses):
            if section.currency != self.scope.currency:
                raise ValueError("section currency must match income statement scope currency")

    def revenue_total(self) -> Money:
        """Return positive absolute total revenue amount."""
        return self.revenues.total_amount()

    def expense_total(self) -> Money:
        """Return positive absolute total expense amount."""
        return self.expenses.total_amount()

    def net_result_side(self) -> DebitCreditSide | None:
        """Return CREDIT for profit, DEBIT for loss, None for zero net result."""
        signed = self._net_signed_decimal()
        if signed > 0:
            return DebitCreditSide.CREDIT
        if signed < 0:
            return DebitCreditSide.DEBIT
        return None

    def net_result_amount(self) -> Money:
        """Return positive absolute net result amount."""
        signed = self._net_signed_decimal()
        amount = signed if signed >= 0 else -signed
        return Money(amount=amount, currency=self.scope.currency)

    def _net_signed_decimal(self) -> Decimal:
        return self.revenues.signed_total_decimal() - self.expenses.signed_total_decimal()
