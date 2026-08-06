"""Explicit mapping between JournalEntry domain objects and SQLite rows."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

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


@dataclass(frozen=True, slots=True)
class JournalEntryHeaderRow:
    """SQLite header row payload for one journal entry."""

    id: str
    legal_entity_id: str
    fiscal_year: int
    journal_code: str
    entry_number: str
    posting_date: str
    status: str
    posted_at: str | None
    currency: str
    version: int
    source_entry_id: str | None
    correction_reason: str | None


@dataclass(frozen=True, slots=True)
class JournalEntryLineRow:
    """SQLite line row payload for one journal entry line."""

    entry_id: str
    position: int
    account_number: str
    side: str
    amount: str
    currency: str
    description: str


class JournalEntrySQLiteMapper:
    """Map JournalEntry aggregates to and from SQLite row structures.

    Amounts are stored as canonical Decimal strings to preserve exact accounting
    values without binary floating-point loss.
    """

    def to_header_row(self, entry: JournalEntry) -> JournalEntryHeaderRow:
        return JournalEntryHeaderRow(
            id=entry.id.value,
            legal_entity_id=entry.legal_entity_id.value,
            fiscal_year=entry.fiscal_year.value,
            journal_code=entry.journal_code.value,
            entry_number=entry.reference.value,
            posting_date=entry.posting_date.isoformat(),
            status=entry.status.value,
            posted_at=entry.posted_at.isoformat() if entry.posted_at is not None else None,
            currency=entry.currency().code,
            version=entry.version,
            source_entry_id=(
                entry.correction_of_entry_id.value
                if entry.correction_of_entry_id is not None
                else None
            ),
            correction_reason=(entry.correction_reason.value if entry.correction_reason else None),
        )

    def to_line_rows(self, entry: JournalEntry) -> tuple[JournalEntryLineRow, ...]:
        line_rows: list[JournalEntryLineRow] = []
        for position, line in enumerate(entry.lines):
            line_rows.append(
                JournalEntryLineRow(
                    entry_id=entry.id.value,
                    position=position,
                    account_number=line.account_number.value,
                    side=line.side.value,
                    amount=str(line.amount.amount),
                    currency=line.amount.currency.code,
                    description=line.description,
                ),
            )
        return tuple(line_rows)

    def from_rows(
        self,
        header_row: sqlite3.Row,
        line_rows: list[sqlite3.Row],
    ) -> JournalEntry:
        lines = tuple(self._line_from_row(row) for row in line_rows)

        source_entry_id_raw = (
            str(header_row["source_entry_id"]) if header_row["source_entry_id"] else None
        )
        correction_reason_raw = (
            str(header_row["correction_reason"]) if header_row["correction_reason"] else None
        )
        posted_at_raw = str(header_row["posted_at"]) if header_row["posted_at"] else None

        posted_at = datetime.fromisoformat(posted_at_raw) if posted_at_raw else None

        return JournalEntry(
            id=JournalEntryId(value=str(header_row["id"])),
            legal_entity_id=LegalEntityId(value=str(header_row["legal_entity_id"])),
            fiscal_year=FiscalYear(value=int(header_row["fiscal_year"])),
            journal_code=JournalCode(value=str(header_row["journal_code"])),
            reference=JournalReference(value=str(header_row["entry_number"])),
            posting_date=date.fromisoformat(str(header_row["posting_date"])),
            version=int(header_row["version"]),
            status=JournalEntryStatus(str(header_row["status"])),
            posted_at=posted_at,
            lines=lines,
            correction_of_entry_id=(
                JournalEntryId(value=source_entry_id_raw)
                if source_entry_id_raw is not None
                else None
            ),
            correction_reason=(
                CorrectionReason(value=correction_reason_raw)
                if correction_reason_raw is not None
                else None
            ),
        )

    @staticmethod
    def _line_from_row(row: sqlite3.Row) -> JournalLine:
        money = Money(
            amount=Decimal(str(row["amount"])),
            currency=Currency(code=str(row["currency"])),
        )
        return JournalLine(
            account_number=AccountNumber(value=str(row["account_number"])),
            side=DebitCreditSide(str(row["side"])),
            amount=money,
            description=str(row["description"]),
        )
