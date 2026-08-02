"""Balance sheet projection aggregate."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.money import Money

from .account_classification import AccountClassification
from .balance_sheet_section import BalanceSheetSection
from .current_period_result import CurrentPeriodResult
from .debit_credit_side import DebitCreditSide
from .ledger_scope import LedgerScope


class UnbalancedBalanceSheetError(Exception):
    """Raised when assets do not equal liabilities + equity + period result."""


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    """Immutable balance sheet with current period result kept separate."""

    scope: LedgerScope
    assets: BalanceSheetSection
    liabilities: BalanceSheetSection
    equity: BalanceSheetSection
    current_period_result: CurrentPeriodResult

    def __post_init__(self) -> None:
        if self.assets.classification is not AccountClassification.ASSET:
            raise ValueError("assets section must use ASSET classification")
        if self.liabilities.classification is not AccountClassification.LIABILITY:
            raise ValueError("liabilities section must use LIABILITY classification")
        if self.equity.classification is not AccountClassification.EQUITY:
            raise ValueError("equity section must use EQUITY classification")

        for section in (self.assets, self.liabilities, self.equity):
            if section.currency != self.scope.currency:
                raise ValueError("section currency must match balance sheet scope currency")
        if self.current_period_result.currency != self.scope.currency:
            raise ValueError("current period result currency must match scope currency")

        if not self.is_balanced():
            raise UnbalancedBalanceSheetError(
                "assets must equal liabilities + equity + signed current period result",
            )

    def assets_total(self) -> Money:
        """Return positive absolute asset total amount."""
        return self.assets.total_amount()

    def liabilities_total(self) -> Money:
        """Return positive absolute liabilities total amount."""
        return self.liabilities.total_amount()

    def equity_total(self) -> Money:
        """Return positive absolute equity total amount."""
        return self.equity.total_amount()

    def right_side_total(self) -> Money:
        """Return positive absolute right-side total amount."""
        signed = self._right_side_signed_decimal()
        amount = signed if signed >= 0 else -signed
        return Money(amount=amount, currency=self.scope.currency)

    def is_balanced(self) -> bool:
        """Return whether assets equal liabilities + equity + period result."""
        return self._assets_signed_decimal() == self._right_side_signed_decimal()

    def _assets_signed_decimal(self) -> Decimal:
        return self.assets.signed_total_decimal()

    def _right_side_signed_decimal(self) -> Decimal:
        return (
            self.liabilities.signed_total_decimal()
            + self.equity.signed_total_decimal()
            + self._signed_period_result_decimal()
        )

    def _signed_period_result_decimal(self) -> Decimal:
        amount = self.current_period_result.result_amount.amount
        side = self.current_period_result.result_side
        if side is None:
            return Decimal("0")
        if side is DebitCreditSide.CREDIT:
            return amount
        return -amount
