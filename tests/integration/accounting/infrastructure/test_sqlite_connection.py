"""Integration tests for SQLite connection bootstrap."""

from __future__ import annotations

import sqlite3

from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)


def test_open_connection() -> None:
    config = DatabaseConfig(path=":memory:")
    manager = ConnectionFactory.create(config)

    connection = manager.open()

    assert isinstance(connection, sqlite3.Connection)
    assert manager.is_open

    manager.close()


def test_close_connection() -> None:
    config = DatabaseConfig(path=":memory:")
    manager = ConnectionFactory.create(config)

    connection = manager.open()
    manager.close()

    assert not manager.is_open
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        pass
    else:
        raise AssertionError("expected closed sqlite connection to reject queries")


def test_foreign_keys_enabled() -> None:
    config = DatabaseConfig(path=":memory:")
    manager = ConnectionFactory.create(config)

    connection = manager.open()
    row = connection.execute("PRAGMA foreign_keys").fetchone()

    assert row is not None
    assert row[0] == 1

    manager.close()
