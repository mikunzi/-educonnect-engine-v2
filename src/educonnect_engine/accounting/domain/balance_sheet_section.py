"""Balance sheet section representation and totals."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money

from .account_classification import AccountClassification
from .account_number import AccountNumber
from .balance_sheet_line import BalanceSheetLine
from .debit_credit_side import DebitCreditSide


class BalanceSheetSectionDuplicateAccountError(Exception):
    """Raised when a section contains duplicate account lines."""


_ALLOWED_SECTION_CLASSIFICATIONS = {
    AccountClassification.ASSET,
    AccountClassification.LIABILITY,
    AccountClassification.EQUITY,
}


@dataclass(frozen=True, slots=True)
class BalanceSheetSection:
    """Immutable section of balance sheet lines."""

    classification: AccountClassification
    currency: Currency
    lines: tuple[BalanceSheetLine, ...]

    def __post_init__(self) -> None:
        if self.classification not in _ALLOWED_SECTION_CLASSIFICATIONS:
            raise ValueError("section classification must be ASSET, LIABILITY or EQUITY")

        seen: set[AccountNumber] = set()
        previous: AccountNumber | None = None
        for line in self.lines:
            if line.classification is not self.classification:
                raise ValueError("line classification must match section classification")
            if line.currency != self.currency:
                raise ValueError("line currency must match section currency")
            if line.account_number in seen:
                raise BalanceSheetSectionDuplicateAccountError(
                    "section must not contain duplicate account numbers",
                )
            seen.add(line.account_number)
            if previous is not None and line.account_number.value < previous.value:
                raise ValueError("section lines must be ordered by account number")
            previous = line.account_number

    def total_side(self) -> DebitCreditSide | None:
        """Return side of signed section total."""
        signed = self._signed_total_decimal()
        if signed > 0:
            if self.classification is AccountClassification.ASSET:
                return DebitCreditSide.DEBIT
            return DebitCreditSide.CREDIT
        if signed < 0:
            if self.classification is AccountClassification.ASSET:
                return DebitCreditSide.CREDIT
            return DebitCreditSide.DEBIT
        return None

    def total_amount(self) -> Money:
        """Return positive absolute section total amount."""
        signed = self._signed_total_decimal()
        amount = signed if signed >= 0 else -signed
        return Money(amount=amount, currency=self.currency)

    def signed_total_decimal(self) -> Decimal:
        """Return signed section total for higher-level balancing arithmetic."""
        return self._signed_total_decimal()

    def _signed_total_decimal(self) -> Decimal:
        total = Decimal("0")
        for line in self.lines:
            side = line.contribution_side
            amount = line.contribution_amount.amount
            if side is None:
                continue
            if self.classification is AccountClassification.ASSET:
                if side is DebitCreditSide.DEBIT:
                    total += amount
                else:
                    total -= amount
            else:
                if side is DebitCreditSide.CREDIT:
                    total += amount
                else:
                    total -= amount
        return total
