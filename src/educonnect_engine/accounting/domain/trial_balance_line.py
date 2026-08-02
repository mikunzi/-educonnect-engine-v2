"""Trial balance line projection."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money

from .account_number import AccountNumber
from .debit_credit_side import DebitCreditSide


@dataclass(frozen=True, slots=True)
class TrialBalanceLine:
    """Immutable trial balance line for one account."""

    account_number: AccountNumber
    currency: Currency
    debit_movement: Money
    credit_movement: Money

    def __post_init__(self) -> None:
        if self.debit_movement.currency != self.currency:
            raise ValueError("debit movement currency must match line currency")
        if self.credit_movement.currency != self.currency:
            raise ValueError("credit movement currency must match line currency")
        if self.debit_movement.amount < Decimal("0"):
            raise ValueError("debit movement must be greater than or equal to 0")
        if self.credit_movement.amount < Decimal("0"):
            raise ValueError("credit movement must be greater than or equal to 0")

    @property
    def balance_side(self) -> DebitCreditSide | None:
        """Return debit or credit side for net balance, None when balanced."""
        if self.debit_movement.amount > self.credit_movement.amount:
            return DebitCreditSide.DEBIT
        if self.credit_movement.amount > self.debit_movement.amount:
            return DebitCreditSide.CREDIT
        return None

    @property
    def balance_amount(self) -> Money:
        """Return absolute net balance amount in line currency."""
        if self.debit_movement.amount == self.credit_movement.amount:
            return Money(amount=Decimal("0"), currency=self.currency)
        if self.debit_movement.amount > self.credit_movement.amount:
            return Money(
                amount=self.debit_movement.amount - self.credit_movement.amount,
                currency=self.currency,
            )
        return Money(
            amount=self.credit_movement.amount - self.debit_movement.amount,
            currency=self.currency,
        )
