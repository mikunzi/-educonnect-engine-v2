"""Trial balance projection service."""

from dataclasses import dataclass

from .ledger import Ledger
from .trial_balance import TrialBalance, TrialBalanceCurrencyMismatchError
from .trial_balance_line import TrialBalanceLine


@dataclass(frozen=True, slots=True)
class TrialBalanceProjectionService:
    """Project deterministic trial balance from an existing ledger only."""

    def project(self, *, ledger: Ledger) -> TrialBalance:
        lines: list[TrialBalanceLine] = []

        for account in ledger.accounts:
            if account.currency != ledger.scope.currency:
                raise TrialBalanceCurrencyMismatchError(
                    "ledger account currency must match ledger scope currency",
                )
            lines.append(
                TrialBalanceLine(
                    account_number=account.account_number,
                    currency=ledger.scope.currency,
                    debit_movement=account.total_debit,
                    credit_movement=account.total_credit,
                ),
            )

        ordered_lines = tuple(sorted(lines, key=lambda line: line.account_number.value))
        return TrialBalance(scope=ledger.scope, lines=ordered_lines)
