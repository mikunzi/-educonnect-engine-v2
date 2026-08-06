"""Unit tests for OpeningEntry."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from educonnect_engine.accounting.domain.opening_entry import (
    OpeningEntry,
    OpeningEntryFiscalYearSequenceError,
    OpeningEntryJournalEntryError,
    OpeningEntryScopeMismatchError,
    OpeningEntryTransitionError,
    OpeningEntryVersionConflictError,
)
from educonnect_engine.accounting.domain.opening_entry_status import OpeningEntryStatus

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.year_end_snapshot_id import YearEndSnapshotId
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _line(account: str, side: DebitCreditSide, amount: str) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code="CHF")),
        description="Opening balance",
    )


def _journal_entry(
    *,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2027,
    posting_date: date = date(2027, 1, 1),
) -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-OPEN-2027"),
        legal_entity_id=LegalEntityId(value=legal_entity_id),
        fiscal_year=FiscalYear(value=fiscal_year),
        journal_code=JournalCode(value="OPEN"),
        reference=JournalReference(value="OPEN-2027"),
        posting_date=posting_date,
        lines=(
            _line("1000", DebitCreditSide.DEBIT, "100.00"),
            _line("2000", DebitCreditSide.CREDIT, "100.00"),
        ),
    )


def _opening_entry(*, journal_entry: JournalEntry | None = None) -> OpeningEntry:
    return OpeningEntry.generate(
        source_snapshot_id=YearEndSnapshotId(value="YES-2026-001"),
        source_legal_entity_id=LegalEntityId(value="entity-01"),
        source_fiscal_year=FiscalYear(value=2026),
        journal_entry=journal_entry or _journal_entry(),
    )


def test_opening_entry_generate_creates_generated_version_zero() -> None:
    journal_entry = _journal_entry()

    opening_entry = _opening_entry(journal_entry=journal_entry)

    assert opening_entry.source_snapshot_id == YearEndSnapshotId(value="YES-2026-001")
    assert opening_entry.source_fiscal_year == FiscalYear(value=2026)
    assert opening_entry.target_fiscal_year == FiscalYear(value=2027)
    assert opening_entry.legal_entity_id == LegalEntityId(value="entity-01")
    assert opening_entry.journal_entry == journal_entry
    assert opening_entry.status is OpeningEntryStatus.GENERATED
    assert opening_entry.version == 0


def test_opening_entry_is_frozen_and_slotted() -> None:
    opening_entry = _opening_entry()

    with pytest.raises(FrozenInstanceError):
        type(opening_entry).__setattr__(opening_entry, "version", 1)

    assert not hasattr(opening_entry, "__dict__")


def test_opening_entry_rejects_non_consecutive_target_fiscal_year() -> None:
    with pytest.raises(OpeningEntryFiscalYearSequenceError):
        _opening_entry(
            journal_entry=_journal_entry(
                fiscal_year=2028,
                posting_date=date(2028, 1, 1),
            ),
        )


def test_opening_entry_rejects_legal_entity_scope_mismatch() -> None:
    with pytest.raises(OpeningEntryScopeMismatchError):
        _opening_entry(journal_entry=_journal_entry(legal_entity_id="entity-02"))


def test_opening_entry_rejects_posting_date_after_first_day_of_target_year() -> None:
    with pytest.raises(OpeningEntryJournalEntryError):
        _opening_entry(journal_entry=_journal_entry(posting_date=date(2027, 1, 2)))


def test_opening_entry_rejects_already_posted_journal_entry_on_generation() -> None:
    posted = _journal_entry().post(datetime(2027, 1, 1, 9, 0, tzinfo=UTC))

    with pytest.raises(OpeningEntryJournalEntryError):
        _opening_entry(journal_entry=posted)


def test_opening_entry_mark_posted_requires_matching_expected_version() -> None:
    opening_entry = _opening_entry()
    posted_journal_entry = opening_entry.journal_entry.post(
        datetime(2027, 1, 1, 9, 0, tzinfo=UTC),
    )

    with pytest.raises(OpeningEntryVersionConflictError):
        opening_entry.mark_posted(journal_entry=posted_journal_entry, expected_version=1)


def test_opening_entry_mark_posted_transitions_once_and_increments_version() -> None:
    opening_entry = _opening_entry()
    posted_journal_entry = opening_entry.journal_entry.post(
        datetime(2027, 1, 1, 9, 0, tzinfo=UTC),
    )

    posted = opening_entry.mark_posted(
        journal_entry=posted_journal_entry,
        expected_version=0,
    )

    assert posted.status is OpeningEntryStatus.POSTED
    assert posted.journal_entry == posted_journal_entry
    assert posted.version == 1

    with pytest.raises(OpeningEntryTransitionError):
        posted.mark_posted(
            journal_entry=replace(posted_journal_entry, version=2),
            expected_version=1,
        )
