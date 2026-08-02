"""Accounting period aggregate."""

from dataclasses import dataclass, replace
from datetime import date

from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId

from .accounting_period_id import AccountingPeriodId
from .accounting_period_status import AccountingPeriodStatus


class AccountingPeriodDateFiscalYearMismatchError(Exception):
    """Raised when period date range is incompatible with fiscal year."""


class AccountingPeriodTransitionError(Exception):
    """Raised when lifecycle transition is not permitted."""


class AccountingPeriodVersionConflictError(Exception):
    """Raised when expected aggregate version mismatches current version."""


@dataclass(frozen=True, slots=True)
class AccountingPeriod:
    """Immutable accounting period aggregate for one entity and fiscal year."""

    id: AccountingPeriodId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    start_date: date
    end_date: date
    status: AccountingPeriodStatus
    version: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, AccountingPeriodStatus):
            raise ValueError("accounting period status must be an AccountingPeriodStatus")
        if self.version < 0:
            raise ValueError("accounting period version must be greater than or equal to 0")
        if self.start_date > self.end_date:
            raise ValueError("accounting period start_date must be before or equal to end_date")
        if (
            self.start_date.year != self.fiscal_year.value
            or self.end_date.year != self.fiscal_year.value
        ):
            raise AccountingPeriodDateFiscalYearMismatchError(
                "accounting period dates must belong to fiscal year",
            )

    def is_open_for(self, posting_date: date) -> bool:
        """Return whether period accepts posting date in OPEN status."""
        return (
            self.status is AccountingPeriodStatus.OPEN
            and self.start_date <= posting_date <= self.end_date
            and posting_date.year == self.fiscal_year.value
        )

    def close(self, *, expected_version: int) -> AccountingPeriod:
        """Close an OPEN period and increment version."""
        if expected_version != self.version:
            raise AccountingPeriodVersionConflictError("accounting period version mismatch")
        if self.status is not AccountingPeriodStatus.OPEN:
            raise AccountingPeriodTransitionError("only OPEN period can be closed")
        return replace(
            self,
            status=AccountingPeriodStatus.CLOSED,
            version=self.version + 1,
        )

    def lock(self, *, expected_version: int) -> AccountingPeriod:
        """Lock a CLOSED period definitively and increment version."""
        if expected_version != self.version:
            raise AccountingPeriodVersionConflictError("accounting period version mismatch")
        if self.status is not AccountingPeriodStatus.CLOSED:
            raise AccountingPeriodTransitionError("only CLOSED period can be locked")
        return replace(
            self,
            status=AccountingPeriodStatus.LOCKED,
            version=self.version + 1,
        )

    def overlaps(self, other: AccountingPeriod) -> bool:
        """Return whether two periods overlap inclusively in same scope."""
        if self.legal_entity_id != other.legal_entity_id:
            return False
        if self.fiscal_year != other.fiscal_year:
            return False
        return not (self.end_date < other.start_date or other.end_date < self.start_date)
