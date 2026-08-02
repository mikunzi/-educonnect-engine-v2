"""Trial balance projection aggregate."""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.shared.value_objects.money import Money

from .account_number import AccountNumber
from .ledger_scope import LedgerScope
from .trial_balance_line import TrialBalanceLine


class TrialBalanceDuplicateAccountError(Exception):
    """Raised when trial balance contains duplicate account lines."""


class TrialBalanceAccountOrderError(Exception):
    """Raised when trial balance lines are not sorted by account number."""


class TrialBalanceCurrencyMismatchError(Exception):
    """Raised when line currency differs from trial balance scope currency."""


class TrialBalanceUnbalancedTotalsError(Exception):
    """Raised when total debit differs from total credit."""


@dataclass(frozen=True, slots=True)
class TrialBalance:
    """Immutable trial balance for one explicit ledger scope."""

    scope: LedgerScope
    lines: tuple[TrialBalanceLine, ...]

    def __post_init__(self) -> None:
        previous: AccountNumber | None = None
        seen: set[AccountNumber] = set()

        for line in self.lines:
            if line.currency != self.scope.currency:
                raise TrialBalanceCurrencyMismatchError(
                    "trial balance line currency must match scope currency",
                )
            if line.account_number in seen:
                raise TrialBalanceDuplicateAccountError(
                    "trial balance must not contain duplicate account numbers",
                )
            seen.add(line.account_number)
            if previous is not None and line.account_number.value < previous.value:
                raise TrialBalanceAccountOrderError(
                    "trial balance lines must be ordered by account number",
                )
            previous = line.account_number

        if self.total_debit().amount != self.total_credit().amount:
            raise TrialBalanceUnbalancedTotalsError(
                "trial balance total debit must equal total credit",
            )

    def get_line(self, account_number: AccountNumber) -> TrialBalanceLine | None:
        """Return trial balance line for account number if present."""
        for line in self.lines:
            if line.account_number == account_number:
                return line
        return None

    def total_debit(self) -> Money:
        """Return total debit movement across all lines."""
        total = sum((line.debit_movement.amount for line in self.lines), start=Decimal("0"))
        return Money(amount=total, currency=self.scope.currency)

    def total_credit(self) -> Money:
        """Return total credit movement across all lines."""
        total = sum((line.credit_movement.amount for line in self.lines), start=Decimal("0"))
        return Money(amount=total, currency=self.scope.currency)

    def is_balanced(self) -> bool:
        """Return whether total debit equals total credit."""
        return self.total_debit().amount == self.total_credit().amount
