"""Opening entry domain artifact."""

from dataclasses import dataclass, replace
from datetime import date

from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId

from .journal_entry import JournalEntry
from .journal_entry_status import JournalEntryStatus
from .opening_entry_status import OpeningEntryStatus
from .year_end_snapshot_id import YearEndSnapshotId


class OpeningEntryFiscalYearSequenceError(Exception):
    """Raised when the target year does not immediately follow the source year."""


class OpeningEntryJournalEntryError(Exception):
    """Raised when the journal entry is incompatible with opening-entry rules."""


class OpeningEntryScopeMismatchError(Exception):
    """Raised when source and target legal entities differ."""


class OpeningEntryTransitionError(Exception):
    """Raised when an opening-entry lifecycle transition is forbidden."""


class OpeningEntryVersionConflictError(Exception):
    """Raised when an expected opening-entry version does not match."""


@dataclass(frozen=True, slots=True)
class OpeningEntry:
    """Immutable opening entry traced to one year-end snapshot."""

    source_snapshot_id: YearEndSnapshotId
    source_legal_entity_id: LegalEntityId
    source_fiscal_year: FiscalYear
    journal_entry: JournalEntry
    status: OpeningEntryStatus
    version: int

    @classmethod
    def generate(
        cls,
        *,
        source_snapshot_id: YearEndSnapshotId,
        source_legal_entity_id: LegalEntityId,
        source_fiscal_year: FiscalYear,
        journal_entry: JournalEntry,
    ) -> OpeningEntry:
        """Create a generated opening entry from a recorded journal entry."""
        return cls(
            source_snapshot_id=source_snapshot_id,
            source_legal_entity_id=source_legal_entity_id,
            source_fiscal_year=source_fiscal_year,
            journal_entry=journal_entry,
            status=OpeningEntryStatus.GENERATED,
            version=0,
        )

    def __post_init__(self) -> None:
        if self.version < 0:
            raise ValueError("opening entry version must be greater than or equal to 0")
        if self.journal_entry.legal_entity_id != self.source_legal_entity_id:
            raise OpeningEntryScopeMismatchError(
                "opening journal entry must use the source legal entity",
            )
        if self.journal_entry.fiscal_year.value != self.source_fiscal_year.value + 1:
            raise OpeningEntryFiscalYearSequenceError(
                "opening journal entry fiscal year must immediately follow source fiscal year",
            )
        expected_date = date(self.journal_entry.fiscal_year.value, 1, 1)
        if self.journal_entry.posting_date != expected_date:
            raise OpeningEntryJournalEntryError(
                "opening journal entry must be posted on first day of target fiscal year",
            )
        expected_journal_status = (
            JournalEntryStatus.RECORDED
            if self.status is OpeningEntryStatus.GENERATED
            else JournalEntryStatus.POSTED
        )
        if self.journal_entry.status is not expected_journal_status:
            raise OpeningEntryJournalEntryError(
                "journal entry status must match opening entry status",
            )

    @property
    def target_fiscal_year(self) -> FiscalYear:
        """Return the target fiscal year."""
        return self.journal_entry.fiscal_year

    @property
    def legal_entity_id(self) -> LegalEntityId:
        """Return the opening entry legal entity."""
        return self.journal_entry.legal_entity_id

    def mark_posted(
        self,
        *,
        journal_entry: JournalEntry,
        expected_version: int,
    ) -> OpeningEntry:
        """Attach the posted journal entry and finalize the opening entry."""
        if expected_version != self.version:
            raise OpeningEntryVersionConflictError("opening entry version mismatch")
        if self.status is not OpeningEntryStatus.GENERATED:
            raise OpeningEntryTransitionError("only a GENERATED opening entry can be posted")
        if journal_entry.status is not JournalEntryStatus.POSTED:
            raise OpeningEntryJournalEntryError("opening journal entry must be POSTED")
        if (
            journal_entry.id != self.journal_entry.id
            or journal_entry.lines != self.journal_entry.lines
        ):
            raise OpeningEntryJournalEntryError(
                "posted journal entry must match generated opening journal entry",
            )
        return replace(
            self,
            journal_entry=journal_entry,
            status=OpeningEntryStatus.POSTED,
            version=self.version + 1,
        )
