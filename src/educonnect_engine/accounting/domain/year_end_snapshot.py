"""Immutable year-end accounting snapshot."""

from dataclasses import dataclass
from datetime import UTC, datetime

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId

from .financial_statements import FinancialStatements
from .trial_balance import TrialBalance
from .year_end_snapshot_id import YearEndSnapshotId


class YearEndSnapshotScopeMismatchError(Exception):
    """Raised when snapshot projections do not share entity and fiscal year."""


class YearEndSnapshotCurrencyMismatchError(Exception):
    """Raised when snapshot projections do not share the same currency."""


class YearEndSnapshotSourceVersionError(Exception):
    """Raised when the snapshot source revision is invalid."""


class YearEndSnapshotTimestampError(Exception):
    """Raised when the capture timestamp is not strictly UTC."""


@dataclass(frozen=True, slots=True)
class YearEndSnapshot:
    """Frozen accounting state used to prepare year-end closing entries."""

    id: YearEndSnapshotId
    trial_balance: TrialBalance
    financial_statements: FinancialStatements
    source_version: int
    captured_at: datetime

    @classmethod
    def capture(
        cls,
        *,
        id: YearEndSnapshotId,
        trial_balance: TrialBalance,
        financial_statements: FinancialStatements,
        source_version: int,
        captured_at: datetime,
    ) -> YearEndSnapshot:
        """Capture already-built projections without recalculating them."""
        return cls(
            id=id,
            trial_balance=trial_balance,
            financial_statements=financial_statements,
            source_version=source_version,
            captured_at=captured_at,
        )

    def __post_init__(self) -> None:
        trial_scope = self.trial_balance.scope
        statement_scope = self.financial_statements.balance_sheet.scope
        if (
            trial_scope.legal_entity_id != statement_scope.legal_entity_id
            or trial_scope.fiscal_year != statement_scope.fiscal_year
        ):
            raise YearEndSnapshotScopeMismatchError(
                "trial balance and financial statements must share entity and fiscal year",
            )
        if trial_scope.currency != statement_scope.currency:
            raise YearEndSnapshotCurrencyMismatchError(
                "trial balance and financial statements must share currency",
            )
        if self.source_version < 0:
            raise YearEndSnapshotSourceVersionError(
                "year-end snapshot source version must be greater than or equal to 0",
            )
        if self.captured_at.tzinfo is None or self.captured_at.tzinfo is not UTC:
            raise YearEndSnapshotTimestampError("year-end snapshot captured_at must use UTC")

    @property
    def legal_entity_id(self) -> LegalEntityId:
        """Return the captured legal entity."""
        return self.trial_balance.scope.legal_entity_id

    @property
    def fiscal_year(self) -> FiscalYear:
        """Return the captured fiscal year."""
        return self.trial_balance.scope.fiscal_year

    @property
    def currency(self) -> Currency:
        """Return the captured accounting currency."""
        return self.trial_balance.scope.currency
