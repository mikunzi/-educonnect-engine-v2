"""SQLite Unit Of Work for accounting transaction coordination."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Protocol

from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodLifecycleRepository,
    AccountRepository,
    JournalEntryRepository,
    UnitOfWork,
)
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    DatabaseConfig,
)
from educonnect_engine.accounting.infrastructure.sqlite.repositories import (
    SQLiteAccountingPeriodRepository,
    SQLiteAccountRepository,
    SQLiteJournalEntryRepository,
)


class _SQLiteConnection(Protocol):
    def execute(self, sql: str) -> object:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class _SQLiteConnectionManager(Protocol):
    def open(self) -> sqlite3.Connection:
        ...

    def close(self) -> None:
        ...


class _SQLiteConnectionFactory(Protocol):
    def create(self, config: DatabaseConfig) -> _SQLiteConnectionManager:
        ...


class SQLiteUnitOfWork(UnitOfWork):
    """Coordinate one SQLite transaction and shared repositories per use case."""

    def __init__(
        self,
        connection_factory: _SQLiteConnectionFactory,
        config: DatabaseConfig,
        account_repository_builder: Callable[[sqlite3.Connection], AccountRepository] = (
            SQLiteAccountRepository
        ),
        accounting_period_repository_builder: Callable[
            [sqlite3.Connection], AccountingPeriodLifecycleRepository
        ] = SQLiteAccountingPeriodRepository,
        journal_entry_repository_builder: Callable[[sqlite3.Connection], JournalEntryRepository] = (
            SQLiteJournalEntryRepository
        ),
    ) -> None:
        self._connection_factory = connection_factory
        self._config = config
        self._account_repository_builder = account_repository_builder
        self._accounting_period_repository_builder = accounting_period_repository_builder
        self._journal_entry_repository_builder = journal_entry_repository_builder

        self._manager: _SQLiteConnectionManager | None = None
        self._connection: _SQLiteConnection | None = None
        self._transaction_active = False

        self._account_repository: AccountRepository | None = None
        self._accounting_period_repository: AccountingPeriodLifecycleRepository | None = None
        self._journal_entry_repository: JournalEntryRepository | None = None

    @property
    def account_repository(self) -> AccountRepository:
        """Return account repository bound to the active transaction connection."""
        if self._account_repository is None:
            raise RuntimeError("transaction is not active")
        return self._account_repository

    @property
    def accounting_period_repository(self) -> AccountingPeriodLifecycleRepository:
        """Return accounting period repository bound to active transaction."""
        if self._accounting_period_repository is None:
            raise RuntimeError("transaction is not active")
        return self._accounting_period_repository

    @property
    def journal_entry_repository(self) -> JournalEntryRepository:
        """Return journal entry repository bound to the active transaction."""
        if self._journal_entry_repository is None:
            raise RuntimeError("transaction is not active")
        return self._journal_entry_repository

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Open one transaction boundary with automatic commit or rollback."""
        if self._transaction_active:
            raise RuntimeError("transaction already active")

        self._start_transaction()
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise
        finally:
            self.close()

    def commit(self) -> None:
        """Commit current transaction when active."""
        if self._connection is None or not self._transaction_active:
            raise RuntimeError("transaction is not active")
        self._connection.commit()

    def rollback(self) -> None:
        """Rollback current transaction when active."""
        if self._connection is None or not self._transaction_active:
            raise RuntimeError("transaction is not active")
        self._connection.rollback()

    def close(self) -> None:
        """Close manager connection and release transaction-scoped repositories."""
        try:
            if self._manager is not None:
                self._manager.close()
        finally:
            self._manager = None
            self._connection = None
            self._transaction_active = False
            self._account_repository = None
            self._accounting_period_repository = None
            self._journal_entry_repository = None

    def _start_transaction(self) -> None:
        self._manager = self._connection_factory.create(self._config)
        self._connection = self._manager.open()
        self._connection.execute("BEGIN")
        self._transaction_active = True

        self._account_repository = self._account_repository_builder(self._connection)
        self._accounting_period_repository = self._accounting_period_repository_builder(
            self._connection,
        )
        self._journal_entry_repository = self._journal_entry_repository_builder(self._connection)


__all__ = ["SQLiteUnitOfWork"]