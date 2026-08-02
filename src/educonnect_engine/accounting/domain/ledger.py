"""Ledger projection aggregate."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.money import Money

from .account_number import AccountNumber
from .ledger_account import LedgerAccount
from .ledger_line import LedgerLine
from .ledger_scope import LedgerScope


@dataclass(frozen=True, slots=True)
class Ledger:
    """Immutable ledger projection for one explicit scope."""

    scope: LedgerScope
    accounts: tuple[LedgerAccount, ...]

    def __post_init__(self) -> None:
        previous: AccountNumber | None = None
        seen: set[AccountNumber] = set()
        for account in self.accounts:
            if account.currency != self.scope.currency:
                raise ValueError("ledger account currency must match ledger scope currency")
            if account.account_number in seen:
                raise ValueError("ledger must not contain duplicate account numbers")
            seen.add(account.account_number)
            if previous is not None and account.account_number.value < previous.value:
                raise ValueError("ledger accounts must be ordered by account number")
            previous = account.account_number

    def get_account(self, account_number: AccountNumber) -> LedgerAccount | None:
        """Return projected account by account number, if any."""
        for account in self.accounts:
            if account.account_number == account_number:
                return account
        return None

    def lines(self) -> tuple[LedgerLine, ...]:
        """Return all ledger lines in deterministic global order."""
        all_lines = tuple(line for account in self.accounts for line in account.lines)
        return tuple(sorted(all_lines, key=lambda line: line.sort_key()))

    def total_debit(self) -> Money:
        """Return total debit amount over all projected accounts."""
        total = sum((account.total_debit.amount for account in self.accounts), start=Decimal("0"))
        return Money(amount=total, currency=self.scope.currency)

    def total_credit(self) -> Money:
        """Return total credit amount over all projected accounts."""
        total = sum((account.total_credit.amount for account in self.accounts), start=Decimal("0"))
        return Money(amount=total, currency=self.scope.currency)
