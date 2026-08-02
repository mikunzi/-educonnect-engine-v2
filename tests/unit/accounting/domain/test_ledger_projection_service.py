"""Unit tests for LedgerProjectionService."""

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
from educonnect_engine.accounting.domain.ledger_projection_service import (
    LedgerCurrencyMismatchError,
    LedgerProjectionService,
    LedgerScopeMismatchError,
    UnpostedJournalEntryProjectionError,
)
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


def _scope(
    *,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2026,
    currency: str = "CHF",
) -> LedgerScope:
    return LedgerScope(
        legal_entity_id=LegalEntityId(value=legal_entity_id),
        fiscal_year=FiscalYear(value=fiscal_year),
        currency=Currency(code=currency),
    )


def _line(
    *,
    account: str,
    side: DebitCreditSide,
    amount: str,
    currency: str = "CHF",
    description: str = "line",
) -> JournalLine:
    return JournalLine(
        account_number=AccountNumber(value=account),
        side=side,
        amount=Money(amount=Decimal(amount), currency=Currency(code=currency)),
        description=description,
    )


def _recorded_entry(
    *,
    entry_id: str,
    posting_date: date,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2026,
    currency: str = "CHF",
    reference: str | None = None,
) -> JournalEntry:
    ref = reference if reference is not None else f"REF-{entry_id}"
    return JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
        legal_entity_id=LegalEntityId(value=legal_entity_id),
        fiscal_year=FiscalYear(value=fiscal_year),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value=ref),
        posting_date=posting_date,
        lines=(
            _line(account="1000", side=DebitCreditSide.DEBIT, amount="10.00", currency=currency),
            _line(account="2000", side=DebitCreditSide.CREDIT, amount="10.00", currency=currency),
        ),
    )


def _posted_entry(
    *,
    entry_id: str,
    posting_date: date,
    posted_at: datetime,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2026,
    currency: str = "CHF",
) -> JournalEntry:
    return _recorded_entry(
        entry_id=entry_id,
        posting_date=posting_date,
        legal_entity_id=legal_entity_id,
        fiscal_year=fiscal_year,
        currency=currency,
    ).post(posted_at=posted_at)


def test_project_returns_empty_ledger_for_empty_entries() -> None:
    service = LedgerProjectionService()

    ledger = service.project(scope=_scope(), entries=())

    assert ledger.scope == _scope()
    assert ledger.accounts == ()


def test_project_rejects_unposted_entry() -> None:
    service = LedgerProjectionService()
    recorded = _recorded_entry(entry_id="JE-001", posting_date=date(2026, 2, 1))

    with pytest.raises(UnpostedJournalEntryProjectionError, match="POSTED"):
        service.project(scope=_scope(), entries=(recorded,))


def test_project_rejects_inconsistent_posted_entry_without_posted_at() -> None:
    service = LedgerProjectionService()
    broken = object.__new__(JournalEntry)
    object.__setattr__(broken, "status", JournalEntryStatus.POSTED)
    object.__setattr__(broken, "posted_at", None)

    with pytest.raises(UnpostedJournalEntryProjectionError, match="posted_at"):
        service.project(scope=_scope(), entries=(broken,))


def test_project_rejects_legal_entity_scope_mismatch() -> None:
    service = LedgerProjectionService()
    posted = _posted_entry(
        entry_id="JE-001",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        legal_entity_id="entity-02",
    )

    with pytest.raises(LedgerScopeMismatchError, match="legal_entity"):
        service.project(scope=_scope(legal_entity_id="entity-01"), entries=(posted,))


def test_project_rejects_fiscal_year_scope_mismatch() -> None:
    service = LedgerProjectionService()
    posted = _posted_entry(
        entry_id="JE-001",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        fiscal_year=2027,
    )

    with pytest.raises(LedgerScopeMismatchError, match="fiscal_year"):
        service.project(scope=_scope(fiscal_year=2026), entries=(posted,))


def test_project_rejects_currency_scope_mismatch() -> None:
    service = LedgerProjectionService()
    posted = _posted_entry(
        entry_id="JE-001",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        currency="EUR",
    )

    with pytest.raises(LedgerCurrencyMismatchError, match="currency"):
        service.project(scope=_scope(currency="CHF"), entries=(posted,))


def test_project_is_deterministic_regardless_of_input_order() -> None:
    service = LedgerProjectionService()
    entry_a = _posted_entry(
        entry_id="JE-001",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
    )
    entry_b = _posted_entry(
        entry_id="JE-002",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    ledger_1 = service.project(scope=_scope(), entries=(entry_a, entry_b))
    ledger_2 = service.project(scope=_scope(), entries=(entry_b, entry_a))

    assert ledger_1 == ledger_2
    assert ledger_1.lines() == ledger_2.lines()


def test_project_treats_reversal_entries_as_regular_posted_entries() -> None:
    service = LedgerProjectionService()
    original = _posted_entry(
        entry_id="JE-001",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    reversal = original.build_reversal(
        reversal_entry_id=JournalEntryId(value="JE-REV"),
        reversal_fiscal_year=FiscalYear(value=2026),
        reversal_journal_code=JournalCode(value="ADJ"),
        reversal_reference=JournalReference(value="REV-001"),
        reversal_date=date(2026, 2, 3),
        correction_reason=CorrectionReason(value="Correction"),
    ).post(posted_at=datetime(2026, 2, 3, 12, 0, tzinfo=UTC))

    ledger = service.project(scope=_scope(), entries=(original, reversal))

    assert ledger.total_debit() == Money(amount=Decimal("20.00"), currency=Currency(code="CHF"))
    assert ledger.total_credit() == Money(amount=Decimal("20.00"), currency=Currency(code="CHF"))


def test_project_does_not_mutate_input_entries() -> None:
    service = LedgerProjectionService()
    entry = _posted_entry(
        entry_id="JE-001",
        posting_date=date(2026, 2, 1),
        posted_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
    )
    before = entry

    _ = service.project(scope=_scope(), entries=(entry,))

    assert entry == before
