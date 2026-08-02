"""Ledger account projection."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.money import Money

from .account_number import AccountNumber
from .debit_credit_side import DebitCreditSide
from .ledger_line import LedgerLine


@dataclass(frozen=True, slots=True)
class LedgerAccount:
    """Projected account view with deterministic line ordering."""

    account_number: AccountNumber
    currency: Currency
    lines: tuple[LedgerLine, ...]

    def __post_init__(self) -> None:
        for line in self.lines:
            if line.account_number != self.account_number:
                raise ValueError("ledger line account_number does not match ledger account")
            if line.amount.currency != self.currency:
                raise ValueError("ledger line currency does not match ledger account currency")

        expected_order = tuple(sorted(self.lines, key=lambda line: line.sort_key()))
        if self.lines != expected_order:
            raise ValueError("ledger lines must already be in deterministic order")

    @property
    def total_debit(self) -> Money:
        """Return total debit amount for this account."""
        total = sum(
            (line.amount.amount for line in self.lines if line.side is DebitCreditSide.DEBIT),
            start=Decimal("0"),
        )
        return Money(amount=total, currency=self.currency)

    @property
    def total_credit(self) -> Money:
        """Return total credit amount for this account."""
        total = sum(
            (line.amount.amount for line in self.lines if line.side is DebitCreditSide.CREDIT),
            start=Decimal("0"),
        )
        return Money(amount=total, currency=self.currency)

    @property
    def balance_side(self) -> DebitCreditSide | None:
        """Return net balance side or None when balanced."""
        debit = self.total_debit.amount
        credit = self.total_credit.amount
        if debit > credit:
            return DebitCreditSide.DEBIT
        if credit > debit:
            return DebitCreditSide.CREDIT
        return None

    @property
    def balance_amount(self) -> Money:
        """Return absolute net balance amount in account currency."""
        debit = self.total_debit.amount
        credit = self.total_credit.amount
        if debit == credit:
            return Money(amount=Decimal("0"), currency=self.currency)
        if debit > credit:
            return Money(amount=debit - credit, currency=self.currency)
        return Money(amount=credit - debit, currency=self.currency)
