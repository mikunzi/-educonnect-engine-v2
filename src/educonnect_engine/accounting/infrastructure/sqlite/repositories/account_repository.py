"""SQLite adapter for the Account repository port."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from educonnect_engine.accounting.domain.account import Account
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.repositories import AccountRepository
from educonnect_engine.accounting.infrastructure.sqlite.mappers.account_mapper import (
    AccountSQLiteMapper,
)


class SQLiteAccountRepository(AccountRepository):
    """Persist and load Account aggregates with explicit SQLite mappings."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._mapper = AccountSQLiteMapper()
        self._savepoint_index = 0

    def add(self, account: Account) -> None:
        row = self._mapper.to_row(account)
        with self._atomic_section():
            try:
                self._connection.execute(
                    """
                    INSERT INTO accounts(account_number, name, category, classification, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row.account_number,
                        row.name,
                        row.category,
                        row.classification,
                        row.is_active,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("account already exists") from exc

    def get_by_number(self, account_number: AccountNumber) -> Account | None:
        row = self._connection.execute(
            """
            SELECT account_number, name, category, classification, is_active
            FROM accounts
            WHERE account_number = ?
            """,
            (account_number.value,),
        ).fetchone()
        if row is None:
            return None
        return self._mapper.from_row(row)

    @contextmanager
    def _atomic_section(self) -> Iterator[None]:
        self._savepoint_index += 1
        savepoint_name = f"account_sp_{self._savepoint_index}"
        self._connection.execute(f"SAVEPOINT {savepoint_name}")
        try:
            yield
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        except Exception:
            self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            self._connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            raise