"""SQLite adapter for LedgerProjection repository port."""

from __future__ import annotations

import sqlite3

from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.repositories import LedgerProjectionRepository
from educonnect_engine.accounting.infrastructure.sqlite.mappers.journal_entry_mapper import (
    JournalEntrySQLiteMapper,
)


class SQLiteLedgerProjectionRepository(LedgerProjectionRepository):
    """Load posted journal entries for one explicit ledger scope."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._mapper = JournalEntrySQLiteMapper()

    def get_posted_entries(self, scope: LedgerScope) -> tuple[JournalEntry, ...]:
        header_rows = self._connection.execute(
            """
            SELECT
                id,
                legal_entity_id,
                fiscal_year,
                journal_code,
                entry_number,
                posting_date,
                status,
                posted_at,
                currency,
                version,
                source_entry_id,
                correction_reason
            FROM journal_entries
            WHERE legal_entity_id = ?
              AND fiscal_year = ?
              AND currency = ?
              AND status = ?
            ORDER BY posting_date ASC, posted_at ASC, id ASC
            """,
            (
                scope.legal_entity_id.value,
                scope.fiscal_year.value,
                scope.currency.code,
                "posted",
            ),
        ).fetchall()

        entries: list[JournalEntry] = []
        for header_row in header_rows:
            line_rows = self._connection.execute(
                """
                SELECT
                    entry_id,
                    position,
                    account_number,
                    side,
                    amount,
                    currency,
                    description
                FROM journal_entry_lines
                WHERE entry_id = ?
                ORDER BY position ASC
                """,
                (str(header_row["id"]),),
            ).fetchall()
            entries.append(self._mapper.from_rows(header_row=header_row, line_rows=line_rows))

        return tuple(entries)
