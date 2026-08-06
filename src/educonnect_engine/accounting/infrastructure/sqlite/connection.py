"""SQLite connection bootstrap confined to accounting infrastructure."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Configuration for opening a SQLite connection."""

    path: str
    timeout: float = 5.0
    detect_types: int = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    isolation_level: Literal["DEFERRED", "EXCLUSIVE", "IMMEDIATE"] | None = None
    check_same_thread: bool = True


class SQLiteConnection:
    """Manage one SQLite connection lifecycle."""

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._connection: sqlite3.Connection | None = None

    @property
    def is_open(self) -> bool:
        """Return whether a live connection is currently open."""
        return self._connection is not None

    def open(self) -> sqlite3.Connection:
        """Open and configure the SQLite connection if needed."""
        if self._connection is None:
            connection = sqlite3.connect(
                self._config.path,
                timeout=self._config.timeout,
                detect_types=self._config.detect_types,
                isolation_level=self._config.isolation_level,
                check_same_thread=self._config.check_same_thread,
            )
            connection.execute("PRAGMA foreign_keys = ON")
            self._connection = connection
        return self._connection

    def close(self) -> None:
        """Close the SQLite connection when currently open."""
        if self._connection is None:
            return
        self._connection.close()
        self._connection = None


class ConnectionFactory:
    """Factory for SQLite connection managers."""

    @staticmethod
    def create(config: DatabaseConfig) -> SQLiteConnection:
        """Build a SQLite connection manager from configuration."""
        return SQLiteConnection(config=config)
