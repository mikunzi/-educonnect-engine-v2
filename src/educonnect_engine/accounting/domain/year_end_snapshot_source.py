"""Atomic source used to capture a year-end snapshot."""

from dataclasses import dataclass

from .financial_statements import FinancialStatements
from .trial_balance import TrialBalance


class YearEndSnapshotSourceScopeMismatchError(Exception):
    """Raised when source projections do not share the same accounting scope."""


class YearEndSnapshotSourceVersionError(Exception):
    """Raised when the source revision is invalid."""


@dataclass(frozen=True, slots=True)
class YearEndSnapshotSource:
    """Coherent projections read at one source revision."""

    trial_balance: TrialBalance
    financial_statements: FinancialStatements
    source_version: int

    def __post_init__(self) -> None:
        if self.trial_balance.scope != self.financial_statements.balance_sheet.scope:
            raise YearEndSnapshotSourceScopeMismatchError(
                "trial balance and financial statements must share the same scope",
            )
        if self.source_version < 0:
            raise YearEndSnapshotSourceVersionError(
                "year-end snapshot source version must be greater than or equal to 0",
            )