"""Unit tests for JournalEntry.build_reversal transition."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.correction_reason import CorrectionReason
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


def _recorded_entry() -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-ORIG"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-ORIG"),
        posting_date=date(2026, 1, 31),
        lines=(
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.DEBIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="line1",
            ),
            JournalLine(
                account_number=AccountNumber(value="2000"),
                side=DebitCreditSide.CREDIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="line2",
            ),
        ),
    )


def _posted_entry() -> JournalEntry:
    return _recorded_entry().post(posted_at=datetime(2026, 2, 1, 12, 0, tzinfo=UTC))


def test_build_reversal_creates_recorded_traceable_entry_with_inverted_lines() -> None:
    original = _posted_entry()

    reversal = original.build_reversal(
        reversal_entry_id=JournalEntryId(value="JE-REV"),
        reversal_fiscal_year=FiscalYear(value=2027),
        reversal_journal_code=JournalCode(value="ADJ"),
        reversal_reference=JournalReference(value="REV-001"),
        reversal_date=date(2027, 1, 2),
        correction_reason=CorrectionReason(value="Error in source posting"),
    )

    assert reversal.id == JournalEntryId(value="JE-REV")
    assert reversal.legal_entity_id == original.legal_entity_id
    assert reversal.fiscal_year == FiscalYear(value=2027)
    assert reversal.journal_code == JournalCode(value="ADJ")
    assert reversal.reference == JournalReference(value="REV-001")
    assert reversal.posting_date == date(2027, 1, 2)
    assert reversal.status is JournalEntryStatus.RECORDED
    assert reversal.version == 0
    assert reversal.posted_at is None
    assert reversal.correction_of_entry_id == original.id
    assert reversal.correction_reason == CorrectionReason(value="Error in source posting")
    assert len(reversal.lines) == len(original.lines)

    assert reversal.lines[0].account_number == original.lines[0].account_number
    assert reversal.lines[0].amount == original.lines[0].amount
    assert reversal.lines[0].side is DebitCreditSide.CREDIT

    assert reversal.lines[1].account_number == original.lines[1].account_number
    assert reversal.lines[1].amount == original.lines[1].amount
    assert reversal.lines[1].side is DebitCreditSide.DEBIT


def test_build_reversal_rejects_non_posted_original() -> None:
    with pytest.raises(ValueError, match="POSTED"):
        _recorded_entry().build_reversal(
            reversal_entry_id=JournalEntryId(value="JE-REV"),
            reversal_fiscal_year=FiscalYear(value=2026),
            reversal_journal_code=JournalCode(value="ADJ"),
            reversal_reference=JournalReference(value="REV-001"),
            reversal_date=date(2026, 2, 1),
            correction_reason=CorrectionReason(value="Error"),
        )


def test_build_reversal_rejects_date_before_original_posting_date() -> None:
    with pytest.raises(ValueError, match="reversal_date"):
        _posted_entry().build_reversal(
            reversal_entry_id=JournalEntryId(value="JE-REV"),
            reversal_fiscal_year=FiscalYear(value=2026),
            reversal_journal_code=JournalCode(value="ADJ"),
            reversal_reference=JournalReference(value="REV-001"),
            reversal_date=date(2026, 1, 1),
            correction_reason=CorrectionReason(value="Error"),
        )


def test_build_reversal_rejects_date_incompatible_with_reversal_fiscal_year() -> None:
    with pytest.raises(ValueError, match="fiscal year"):
        _posted_entry().build_reversal(
            reversal_entry_id=JournalEntryId(value="JE-REV"),
            reversal_fiscal_year=FiscalYear(value=2027),
            reversal_journal_code=JournalCode(value="ADJ"),
            reversal_reference=JournalReference(value="REV-001"),
            reversal_date=date(2026, 2, 1),
            correction_reason=CorrectionReason(value="Error"),
        )


def test_build_reversal_rejects_invalid_correction_reason_type() -> None:
    with pytest.raises(ValueError, match="CorrectionReason"):
        _posted_entry().build_reversal(
            reversal_entry_id=JournalEntryId(value="JE-REV"),
            reversal_fiscal_year=FiscalYear(value=2026),
            reversal_journal_code=JournalCode(value="ADJ"),
            reversal_reference=JournalReference(value="REV-001"),
            reversal_date=date(2026, 2, 1),
            correction_reason="wrong",  # type: ignore[arg-type]
        )


def test_journal_entry_rejects_partial_correction_metadata() -> None:
    with pytest.raises(ValueError, match="set together"):
        JournalEntry(
            id=JournalEntryId(value="JE-REV"),
            legal_entity_id=LegalEntityId(value="entity-01"),
            fiscal_year=FiscalYear(value=2026),
            journal_code=JournalCode(value="ADJ"),
            reference=JournalReference(value="REV-001"),
            posting_date=date(2026, 3, 1),
            version=0,
            status=JournalEntryStatus.RECORDED,
            posted_at=None,
            lines=(
                JournalLine(
                    account_number=AccountNumber(value="1000"),
                    side=DebitCreditSide.DEBIT,
                    amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                    description="debit",
                ),
                JournalLine(
                    account_number=AccountNumber(value="2000"),
                    side=DebitCreditSide.CREDIT,
                    amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                    description="credit",
                ),
            ),
            correction_of_entry_id=JournalEntryId(value="JE-ORIG"),
            correction_reason=None,
        )
