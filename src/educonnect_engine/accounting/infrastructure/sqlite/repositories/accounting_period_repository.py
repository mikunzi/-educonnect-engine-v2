"""SQLite adapter for the AccountingPeriod lifecycle repository port."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

from educonnect_engine.accounting.domain.accounting_period import AccountingPeriod
from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId
from educonnect_engine.accounting.domain.repositories import AccountingPeriodLifecycleRepository
from educonnect_engine.accounting.infrastructure.sqlite.mappers.accounting_period_mapper import (
    AccountingPeriodSQLiteMapper,
)
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class SQLiteAccountingPeriodRepository(AccountingPeriodLifecycleRepository):
    """Persist and load AccountingPeriod aggregates with explicit SQLite mappings."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._mapper = AccountingPeriodSQLiteMapper()
        self._savepoint_index = 0

    def is_open(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        posting_date: date,
    ) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM accounting_periods
            WHERE legal_entity_id = ?
              AND fiscal_year = ?
              AND status = ?
              AND start_date <= ?
              AND end_date >= ?
            LIMIT 1
            """,
            (
                legal_entity_id.value,
                fiscal_year.value,
                "open",
                posting_date.isoformat(),
                posting_date.isoformat(),
            ),
        ).fetchone()
        return row is not None

    def get_by_id(self, accounting_period_id: AccountingPeriodId) -> AccountingPeriod | None:
        row = self._connection.execute(
            """
            SELECT
                id,
                legal_entity_id,
                fiscal_year,
                start_date,
                end_date,
                status,
                version
            FROM accounting_periods
            WHERE id = ?
            """,
            (accounting_period_id.value,),
        ).fetchone()
        if row is None:
            return None
        return self._mapper.from_row(row)

    def add(self, period: AccountingPeriod) -> None:
        row = self._mapper.to_row(period)
        with self._atomic_section():
            try:
                self._connection.execute(
                    """
                    INSERT INTO accounting_periods(
                        id,
                        legal_entity_id,
                        fiscal_year,
                        start_date,
                        end_date,
                        status,
                        version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.id,
                        row.legal_entity_id,
                        row.fiscal_year,
                        row.start_date,
                        row.end_date,
                        row.status,
                        row.version,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("accounting period already exists") from exc

    def save(self, period: AccountingPeriod, expected_version: int) -> None:
        row = self._mapper.to_row(period)
        with self._atomic_section():
            result = self._connection.execute(
                """
                UPDATE accounting_periods
                SET
                    legal_entity_id = ?,
                    fiscal_year = ?,
                    start_date = ?,
                    end_date = ?,
                    status = ?,
                    version = ?
                WHERE id = ? AND version = ?
                """,
                (
                    row.legal_entity_id,
                    row.fiscal_year,
                    row.start_date,
                    row.end_date,
                    row.status,
                    row.version,
                    row.id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise ValueError("accounting period version mismatch")

    def has_open_period(self, legal_entity_id: LegalEntityId, fiscal_year: FiscalYear) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM accounting_periods
            WHERE legal_entity_id = ?
              AND fiscal_year = ?
              AND status = ?
            LIMIT 1
            """,
            (legal_entity_id.value, fiscal_year.value, "open"),
        ).fetchone()
        return row is not None

    def has_overlapping_period(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        start_date: date,
        end_date: date,
    ) -> bool:
        start_value = start_date.isoformat()
        end_value = end_date.isoformat()
        row = self._connection.execute(
            """
            SELECT 1
            FROM accounting_periods
            WHERE legal_entity_id = ?
              AND fiscal_year = ?
              AND NOT (end_date < ? OR start_date > ?)
            LIMIT 1
            """,
            (legal_entity_id.value, fiscal_year.value, start_value, end_value),
        ).fetchone()
        return row is not None

    @contextmanager
    def _atomic_section(self) -> Iterator[None]:
        self._savepoint_index += 1
        savepoint_name = f"accounting_period_sp_{self._savepoint_index}"
        self._connection.execute(f"SAVEPOINT {savepoint_name}")
        try:
            yield
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        except Exception:
            self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            raise