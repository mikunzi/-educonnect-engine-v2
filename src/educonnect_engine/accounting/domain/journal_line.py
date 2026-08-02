"""Journal line value object."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.money import Money

from .account_number import AccountNumber
from .debit_credit_side import DebitCreditSide


@dataclass(frozen=True, slots=True)
class JournalLine:
    """Immutable accounting line within a journal entry aggregate."""

    account_number: AccountNumber
    side: DebitCreditSide
    amount: Money
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.account_number, AccountNumber):
            raise TypeError("account_number must be an AccountNumber")
        if not isinstance(self.side, DebitCreditSide):
            raise TypeError("side must be a DebitCreditSide")
        if not isinstance(self.amount, Money):
            raise TypeError("amount must be a Money")
        if self.amount.amount <= Decimal("0"):
            raise ValueError("journal line amount must be strictly positive")
        if not self.description.strip():
            raise ValueError("description must not be empty")
