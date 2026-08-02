"""Unit tests for JournalEntry.post transition."""

from datetime import UTC, date, datetime, timedelta, timezone
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


def _recorded_entry() -> JournalEntry:
    return JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.DEBIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="debit",
            ),
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.CREDIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="credit",
            ),
        ),
    )


def test_journal_entry_post_returns_new_posted_instance() -> None:
    entry = _recorded_entry()
    posted_at = datetime(2026, 1, 31, 12, 0, tzinfo=UTC)

    posted = entry.post(posted_at=posted_at)

    assert posted is not entry
    assert entry.status is JournalEntryStatus.RECORDED
    assert entry.posted_at is None
    assert entry.version == 0
    assert posted.status is JournalEntryStatus.POSTED
    assert posted.posted_at == posted_at
    assert posted.version == 1


def test_journal_entry_post_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _recorded_entry().post(posted_at=datetime(2026, 1, 31, 12, 0))


def test_journal_entry_post_rejects_non_utc_datetime() -> None:
    with pytest.raises(ValueError, match="UTC"):
        _recorded_entry().post(
            posted_at=datetime(2026, 1, 31, 12, 0, tzinfo=timezone(timedelta(hours=1))),
        )


def test_journal_entry_post_rejects_already_posted_entry() -> None:
    posted = _recorded_entry().post(posted_at=datetime(2026, 1, 31, 12, 0, tzinfo=UTC))

    with pytest.raises(ValueError, match="RECORDED"):
        posted.post(posted_at=datetime(2026, 1, 31, 12, 5, tzinfo=UTC))
