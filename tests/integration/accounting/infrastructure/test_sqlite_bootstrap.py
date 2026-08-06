"""Integration tests for SQLite schema bootstrap."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)


class _FailingBootstrap(SQLiteSchemaBootstrap):
    def _load_migration_sql(self, migration_name: str) -> str:
        _ = migration_name
        return "CREATE TABL broken_sql"


def _new_bootstrap(db_path: Path) -> SQLiteSchemaBootstrap:
    return SQLiteSchemaBootstrap(
        connection_factory=ConnectionFactory(),
        config=DatabaseConfig(path=str(db_path)),
    )


def _list_tables(db_path: Path) -> set[str]:
    with sqlite3.connect(str(db_path)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_bootstrap_creates_schema_migrations_and_sets_version(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap.db"
    bootstrap = _new_bootstrap(db_path)

    bootstrap.bootstrap()

    assert bootstrap.current_version() == 1
    tables = _list_tables(db_path)
    assert "schema_migrations" in tables


def test_bootstrap_records_migration_once_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap-idempotent.db"
    bootstrap = _new_bootstrap(db_path)

    bootstrap.bootstrap()
    bootstrap.bootstrap()

    with sqlite3.connect(str(db_path)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 1",
        ).fetchone()

    assert row is not None
    assert row[0] == 1
    assert bootstrap.current_version() == 1


def test_bootstrap_survives_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap-reopen.db"
    bootstrap = _new_bootstrap(db_path)

    bootstrap.bootstrap()

    reopened = _new_bootstrap(db_path)
    reopened.bootstrap()

    assert reopened.current_version() == 1


def test_foreign_keys_enabled_on_bootstrap_connections(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap-foreign-keys.db"
    bootstrap = _new_bootstrap(db_path)

    bootstrap.bootstrap()

    manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    connection = manager.open()
    try:
        row = connection.execute("PRAGMA foreign_keys").fetchone()
    finally:
        manager.close()

    assert row is not None
    assert row[0] == 1


def test_bootstrap_rolls_back_and_does_not_record_version_on_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap-failure.db"
    failing = _FailingBootstrap(
        connection_factory=ConnectionFactory(),
        config=DatabaseConfig(path=str(db_path)),
    )

    try:
        failing.bootstrap()
    except sqlite3.Error:
        pass
    else:
        raise AssertionError("expected sqlite error during failing bootstrap")

    tables = _list_tables(db_path)
    assert "schema_migrations" not in tables

    clean = _new_bootstrap(db_path)
    assert clean.current_version() == 0


def test_bootstrap_creates_no_accounting_business_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "bootstrap-no-business-tables.db"
    bootstrap = _new_bootstrap(db_path)

    bootstrap.bootstrap()

    tables = _list_tables(db_path)
    forbidden = {
        "journal_entries",
        "journal_entry_lines",
        "accounts",
        "accounting_periods",
        "snapshots",
        "opening_entries",
    }

    assert forbidden.isdisjoint(tables)
