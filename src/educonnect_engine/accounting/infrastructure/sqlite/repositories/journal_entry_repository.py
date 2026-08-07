"""SQLite adapter for the JournalEntry repository port."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.repositories import JournalEntryRepository
from educonnect_engine.accounting.infrastructure.sqlite.mappers.journal_entry_mapper import (
    JournalEntrySQLiteMapper,
)


class SQLiteJournalEntryRepository(JournalEntryRepository):
    """Persist and load JournalEntry aggregates with explicit SQLite mappings."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._mapper = JournalEntrySQLiteMapper()
        self._savepoint_index = 0

    def add(self, entry: JournalEntry) -> None:
        with self._atomic_section():
            self._insert_entry(entry)

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        header_row = self._connection.execute(
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
            WHERE id = ?
            """,
            (entry_id.value,),
        ).fetchone()
        if header_row is None:
            return None

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
            (entry_id.value,),
        ).fetchall()

        return self._mapper.from_rows(header_row=header_row, line_rows=line_rows)

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        with self._atomic_section():
            current_row = self._connection.execute(
                "SELECT version FROM journal_entries WHERE id = ?",
                (entry.id.value,),
            ).fetchone()
            if current_row is None:
                raise ValueError("journal entry not found for posting")
            if int(current_row["version"]) != expected_version:
                raise ValueError("journal entry version mismatch")
            if entry.version != expected_version + 1:
                raise ValueError("invalid posted version progression")

            header = self._mapper.to_header_row(entry)
            result = self._connection.execute(
                """
                UPDATE journal_entries
                SET
                    status = ?,
                    posted_at = ?,
                    version = ?,
                    currency = ?,
                    source_entry_id = ?,
                    correction_reason = ?
                WHERE id = ? AND version = ?
                """,
                (
                    header.status,
                    header.posted_at,
                    header.version,
                    header.currency,
                    header.source_entry_id,
                    header.correction_reason,
                    header.id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise ValueError("journal entry version mismatch")

    def save_reversal(
        self,
        reversal_entry: JournalEntry,
        original_entry_id: JournalEntryId,
        expected_original_version: int,
    ) -> None:
        with self._atomic_section():
            original_row = self._connection.execute(
                "SELECT version FROM journal_entries WHERE id = ?",
                (original_entry_id.value,),
            ).fetchone()
            if original_row is None:
                raise ValueError("original journal entry not found")
            if int(original_row["version"]) != expected_original_version:
                raise ValueError("journal entry version mismatch")

            existing_reversal = self._connection.execute(
                "SELECT 1 FROM journal_entries WHERE source_entry_id = ?",
                (original_entry_id.value,),
            ).fetchone()
            if existing_reversal is not None:
                raise ValueError("direct reversal already exists")

            self._insert_entry(reversal_entry)

    def delete_draft(self, entry_id: JournalEntryId, expected_version: int) -> None:
        with self._atomic_section():
            result = self._connection.execute(
                """
                DELETE FROM journal_entries
                WHERE id = ? AND status = ? AND version = ?
                """,
                (entry_id.value, "recorded", expected_version),
            )
            if result.rowcount != 1:
                raise ValueError("journal entry version mismatch")

    def _insert_entry(self, entry: JournalEntry) -> None:
        header = self._mapper.to_header_row(entry)
        line_rows = self._mapper.to_line_rows(entry)

        try:
            self._connection.execute(
                """
                INSERT INTO journal_entries(
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    header.id,
                    header.legal_entity_id,
                    header.fiscal_year,
                    header.journal_code,
                    header.entry_number,
                    header.posting_date,
                    header.status,
                    header.posted_at,
                    header.currency,
                    header.version,
                    header.source_entry_id,
                    header.correction_reason,
                ),
            )

            self._connection.executemany(
                """
                INSERT INTO journal_entry_lines(
                    entry_id,
                    position,
                    account_number,
                    side,
                    amount,
                    currency,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        row.entry_id,
                        row.position,
                        row.account_number,
                        row.side,
                        row.amount,
                        row.currency,
                        row.description,
                    )
                    for row in line_rows
                ],
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("journal entry already exists") from exc

    @contextmanager
    def _atomic_section(self) -> Iterator[None]:
        self._savepoint_index += 1
        savepoint_name = f"journal_entry_sp_{self._savepoint_index}"
        self._connection.execute(f"SAVEPOINT {savepoint_name}")
        try:
            yield
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        except Exception:
            self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            raise
