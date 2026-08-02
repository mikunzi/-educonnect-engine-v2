"""Balance sheet line representation."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money

from .account_classification import AccountClassification
from .account_number import AccountNumber
from .debit_credit_side import DebitCreditSide

_ALLOWED_BALANCE_SHEET_CLASSIFICATIONS = {
    AccountClassification.ASSET,
    AccountClassification.LIABILITY,
    AccountClassification.EQUITY,
}


@dataclass(frozen=True, slots=True)
class BalanceSheetLine:
    """Minimal display line for balance-sheet accounts only."""

    account_number: AccountNumber
    classification: AccountClassification
    currency: Currency
    balance_side: DebitCreditSide | None
    balance_amount: Money

    def __post_init__(self) -> None:
        if self.classification not in _ALLOWED_BALANCE_SHEET_CLASSIFICATIONS:
            raise ValueError("balance sheet line classification must be ASSET, LIABILITY or EQUITY")
        if self.balance_amount.currency != self.currency:
            raise ValueError("balance amount currency must match line currency")
        if self.balance_amount.amount < Decimal("0"):
            raise ValueError("balance amount must be greater than or equal to 0")
        if self.balance_side is None and self.balance_amount.amount != Decimal("0"):
            raise ValueError("balance side must be defined when balance amount is non-zero")

    @property
    def contribution_side(self) -> DebitCreditSide | None:
        """Contribution orientation used by section signed totals."""
        return self.balance_side

    @property
    def contribution_amount(self) -> Money:
        """Positive contribution magnitude used by section signed totals."""
        if self.contribution_side is None:
            return Money(amount=Decimal("0"), currency=self.currency)
        return self.balance_amount
