"""Fiscal year closing aggregate."""

from dataclasses import dataclass, replace

from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId

from .closing_timestamp import ClosingTimestamp
from .fiscal_year_closing_id import FiscalYearClosingId
from .fiscal_year_closing_status import FiscalYearClosingStatus


class FiscalYearClosingTransitionError(Exception):
    """Raised when fiscal year closing transition is not permitted."""


class FiscalYearClosingVersionConflictError(Exception):
    """Raised when expected version does not match current aggregate version."""


@dataclass(frozen=True, slots=True)
class FiscalYearClosing:
    """Immutable fiscal year closing aggregate for one entity and fiscal year."""

    id: FiscalYearClosingId
    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    status: FiscalYearClosingStatus
    closing_timestamp: ClosingTimestamp | None
    version: int

    @classmethod
    def open(
        cls,
        *,
        id: FiscalYearClosingId,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
    ) -> FiscalYearClosing:
        return cls(
            id=id,
            legal_entity_id=legal_entity_id,
            fiscal_year=fiscal_year,
            status=FiscalYearClosingStatus.OPEN,
            closing_timestamp=None,
            version=0,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.status, FiscalYearClosingStatus):
            raise ValueError("fiscal year closing status must be a FiscalYearClosingStatus")
        if self.version < 0:
            raise ValueError("fiscal year closing version must be greater than or equal to 0")
        if self.status is FiscalYearClosingStatus.OPEN and self.closing_timestamp is not None:
            raise ValueError("OPEN fiscal year closing must not define closing_timestamp")
        if self.status is FiscalYearClosingStatus.CLOSED and self.closing_timestamp is None:
            raise ValueError("CLOSED fiscal year closing must define closing_timestamp")

    def close(
        self,
        *,
        timestamp: ClosingTimestamp,
        expected_version: int,
    ) -> FiscalYearClosing:
        if expected_version != self.version:
            raise FiscalYearClosingVersionConflictError("fiscal year closing version mismatch")
        if self.status is not FiscalYearClosingStatus.OPEN:
            raise FiscalYearClosingTransitionError("fiscal year is already closed")
        return replace(
            self,
            status=FiscalYearClosingStatus.CLOSED,
            closing_timestamp=timestamp,
            version=self.version + 1,
        )
