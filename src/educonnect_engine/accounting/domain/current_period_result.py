"""Current period result computed from revenue and expense trial-balance lines."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money

from .debit_credit_side import DebitCreditSide


@dataclass(frozen=True, slots=True)
class CurrentPeriodResult:
    """Net current period result separated from balance sheet account lines."""

    currency: Currency
    revenue_total: Money
    expense_total: Money

    def __post_init__(self) -> None:
        if self.revenue_total.currency != self.currency:
            raise ValueError("revenue total currency must match result currency")
        if self.expense_total.currency != self.currency:
            raise ValueError("expense total currency must match result currency")
        if self.revenue_total.amount < Decimal("0"):
            raise ValueError("revenue total must be greater than or equal to 0")
        if self.expense_total.amount < Decimal("0"):
            raise ValueError("expense total must be greater than or equal to 0")

    @property
    def result_side(self) -> DebitCreditSide | None:
        """Return CREDIT for profit, DEBIT for loss, None for zero result."""
        if self.revenue_total.amount > self.expense_total.amount:
            return DebitCreditSide.CREDIT
        if self.expense_total.amount > self.revenue_total.amount:
            return DebitCreditSide.DEBIT
        return None

    @property
    def result_amount(self) -> Money:
        """Return absolute current period result amount in result currency."""
        if self.revenue_total.amount >= self.expense_total.amount:
            return Money(
                amount=self.revenue_total.amount - self.expense_total.amount,
                currency=self.currency,
            )
        return Money(
            amount=self.expense_total.amount - self.revenue_total.amount,
            currency=self.currency,
        )
