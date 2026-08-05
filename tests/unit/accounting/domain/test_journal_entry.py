"""Unit tests for JournalEntry aggregate."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _line(side: DebitCreditSide, amount: str, currency: str = "CHF") -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value="1000"),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code=currency)),
        description="line",
    )


def test_journal_entry_from_recorded_sets_recorded_status_and_posted_at_none() -> None:
    entry = JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line(DebitCreditSide.DEBIT, "10.00"),
            _line(DebitCreditSide.CREDIT, "10.00"),
        ),
    )

    assert entry.status is JournalEntryStatus.RECORDED
    assert entry.posted_at is None
    assert entry.version == 0


def test_journal_entry_rejects_less_than_two_lines() -> None:
    with pytest.raises(ValueError):
        JournalEntry.from_recorded(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            lines=(_line(DebitCreditSide.DEBIT, "10.00"),),
        )


def test_journal_entry_rejects_unbalanced_totals() -> None:
    with pytest.raises(ValueError):
        JournalEntry.from_recorded(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00"),
                _line(DebitCreditSide.CREDIT, "9.00"),
            ),
        )


def test_journal_entry_rejects_mixed_currencies() -> None:
    with pytest.raises(ValueError):
        JournalEntry.from_recorded(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00", currency="CHF"),
                _line(DebitCreditSide.CREDIT, "10.00", currency="EUR"),
            ),
        )


def test_journal_entry_rejects_non_recorded_status() -> None:
    with pytest.raises(ValueError, match="status"):
        JournalEntry(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            version=0,
            status="posted",  # type: ignore[arg-type]
            posted_at=None,
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00"),
                _line(DebitCreditSide.CREDIT, "10.00"),
            ),
        )


def test_journal_entry_rejects_posted_at_for_recorded_status() -> None:
    with pytest.raises(ValueError, match="posted_at"):
        JournalEntry(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            version=0,
            status=JournalEntryStatus.RECORDED,
            posted_at=datetime(2026, 1, 31, 12, 0, 0),
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00"),
                _line(DebitCreditSide.CREDIT, "10.00"),
            ),
        )


def test_journal_entry_rejects_non_journal_line_items() -> None:
    with pytest.raises(TypeError, match="JournalLine"):
        JournalEntry(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            version=0,
            status=JournalEntryStatus.RECORDED,
            posted_at=None,
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00"),
                object(),  # type: ignore[arg-type]
            ),
        )


def test_journal_entry_rejects_negative_version() -> None:
    with pytest.raises(ValueError, match="version"):
        JournalEntry(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            version=-1,
            status=JournalEntryStatus.RECORDED,
            posted_at=None,
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00"),
                _line(DebitCreditSide.CREDIT, "10.00"),
            ),
        )


def test_journal_entry_rejects_posted_status_without_posted_at() -> None:
    with pytest.raises(ValueError, match="posted entries"):
        JournalEntry(
            id=JournalEntryId(value="JE-001"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="GEN"),
            reference=JournalReference(value="REF-001"),
            posting_date=date(2026, 1, 31),
            version=1,
            status=JournalEntryStatus.POSTED,
            posted_at=None,
            lines=(
                _line(DebitCreditSide.DEBIT, "10.00"),
                _line(DebitCreditSide.CREDIT, "10.00"),
            ),
        )


def test_journal_entry_post_rejects_recorded_state_with_existing_posted_at() -> None:
    inconsistent = object.__new__(JournalEntry)
    object.__setattr__(inconsistent, "id", JournalEntryId(value="JE-001"))
    object.__setattr__(inconsistent, "legal_entity_id", LegalEntityId(value="entity-01"))
    object.__setattr__(inconsistent, "fiscal_year", FiscalYear(value=2026))
    object.__setattr__(inconsistent, "journal_code", JournalCode(value="GEN"))
    object.__setattr__(inconsistent, "reference", JournalReference(value="REF-001"))
    object.__setattr__(inconsistent, "posting_date", date(2026, 1, 31))
    object.__setattr__(inconsistent, "version", 0)
    object.__setattr__(inconsistent, "status", JournalEntryStatus.RECORDED)
    object.__setattr__(inconsistent, "posted_at", datetime(2026, 1, 31, 12, 0))
    object.__setattr__(
        inconsistent,
        "lines",
        (
            _line(DebitCreditSide.DEBIT, "10.00"),
            _line(DebitCreditSide.CREDIT, "10.00"),
        ),
    )

    with pytest.raises(ValueError, match="posted_at"):
        inconsistent.post(posted_at=datetime(2026, 1, 31, 12, 5, tzinfo=UTC))


def test_journal_entry_replace_lines_returns_new_valid_instance() -> None:
    entry = JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line(DebitCreditSide.DEBIT, "10.00"),
            _line(DebitCreditSide.CREDIT, "10.00"),
        ),
    )

    updated = entry.replace_lines(
        (
            _line(DebitCreditSide.DEBIT, "12.00"),
            _line(DebitCreditSide.CREDIT, "12.00"),
        ),
    )

    assert updated is not entry
    assert updated.lines != entry.lines
    assert updated.status is JournalEntryStatus.RECORDED
    assert updated.posted_at is None


def test_journal_entry_is_frozen_and_has_slots() -> None:
    entry = JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            _line(DebitCreditSide.DEBIT, "10.00"),
            _line(DebitCreditSide.CREDIT, "10.00"),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        type(entry).__setattr__(entry, "posted_at", None)

    assert not hasattr(entry, "__dict__")
