"""SQLite schema bootstrap utilities for accounting infrastructure."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from importlib import resources

from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)


class SQLiteSchemaBootstrap:
    """Apply and track the initial SQLite schema migration."""

    def __init__(self, connection_factory: ConnectionFactory, config: DatabaseConfig) -> None:
        self._connection_factory = connection_factory
        self._config = config

    def bootstrap(self) -> None:
        """Create schema migration metadata and apply migration 001 exactly once."""
        manager = self._connection_factory.create(self._config)
        connection = manager.open()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if not self._has_schema_migration_table(connection):
                migration_sql = self._load_migration_sql("001_initial.sql")
                connection.execute(migration_sql)

            if not self._is_migration_applied(connection, 1):
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES(?, ?, ?)",
                    (1, "001_initial.sql", self._utc_now_iso()),
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            manager.close()

    def current_version(self) -> int:
        """Return current schema migration version, or 0 for non-bootstrapped databases."""
        manager = self._connection_factory.create(self._config)
        connection = manager.open()

        try:
            if not self._has_schema_migration_table(connection):
                return 0

            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations",
            ).fetchone()
            if row is None:
                return 0
            return int(row[0])
        finally:
            manager.close()

    def _load_migration_sql(self, migration_name: str) -> str:
        resource_path = resources.files(
            "educonnect_engine.accounting.infrastructure.sqlite.schema",
        ).joinpath(f"migrations/{migration_name}")
        return resource_path.read_text(encoding="utf-8")

    @staticmethod
    def _has_schema_migration_table(connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'",
        ).fetchone()
        return row is not None

    @staticmethod
    def _is_migration_applied(connection: sqlite3.Connection, version: int) -> bool:
        row = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(UTC).isoformat()
