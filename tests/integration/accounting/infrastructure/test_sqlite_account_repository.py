"""Integration tests for SQLiteAccountRepository."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from educonnect_engine.accounting.domain.account import Account
from educonnect_engine.accounting.domain.account_category import AccountCategory
from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)
from educonnect_engine.accounting.infrastructure.sqlite.mappers.account_mapper import (
    AccountRow,
    AccountSQLiteMapper,
)
from educonnect_engine.accounting.infrastructure.sqlite.repositories import (
    SQLiteAccountRepository,
)


class _FailingAccountMapper(AccountSQLiteMapper):
    def to_row(self, account: Account) -> AccountRow:
        row = super().to_row(account)
        return AccountRow(
            account_number="",
            name=row.name,
            category=row.category,
            classification=row.classification,
            is_active=row.is_active,
        )


def _account(number: str = "1000", is_active: bool = True) -> Account:
    return Account(
        number=AccountNumber(value=number),
        name="Cash",
        category=AccountCategory.ASSET,
        classification=AccountClassification.ASSET,
        is_active=is_active,
    )


def _bootstrap_v3(db_path: Path) -> None:
    bootstrap = SQLiteSchemaBootstrap(
        connection_factory=ConnectionFactory(),
        config=DatabaseConfig(path=str(db_path)),
        target_version=3,
    )
    bootstrap.bootstrap()


def _new_repository(db_path: Path) -> tuple[SQLiteAccountRepository, sqlite3.Connection]:
    manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    connection = manager.open()
    repository = SQLiteAccountRepository(connection=connection)
    return repository, connection


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(str(db_path)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_add_and_get_by_number_round_trip_preserves_account_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "account.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    try:
        account = _account()
        repository.add(account)

        loaded = repository.get_by_number(account.number)
        assert loaded is not None
        assert isinstance(loaded, Account)
        assert loaded.number == account.number
        assert loaded.name == account.name
        assert loaded.category is account.category
        assert loaded.classification is account.classification
        assert loaded.is_active is account.is_active
    finally:
        connection.close()


def test_get_by_number_unknown_returns_none(tmp_path: Path) -> None:
    db_path = tmp_path / "account-unknown.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    try:
        missing = repository.get_by_number(AccountNumber(value="2999"))
        assert missing is None
    finally:
        connection.close()


def test_add_duplicate_raises_error(tmp_path: Path) -> None:
    db_path = tmp_path / "account-duplicate.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    try:
        account = _account()
        repository.add(account)

        try:
            repository.add(account)
        except ValueError as exc:
            assert "already exists" in str(exc)
        else:
            raise AssertionError("expected duplicate account error")
    finally:
        connection.close()


def test_add_uses_atomic_savepoint_and_rolls_back_on_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "account-rollback.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository._mapper = _FailingAccountMapper()  # type: ignore[attr-defined]
        account = _account("1200")

        try:
            repository.add(account)
        except ValueError:
            pass
        else:
            raise AssertionError("expected insertion failure")

        row = connection.execute(
            "SELECT 1 FROM accounts WHERE account_number = ?",
            (account.number.value,),
        ).fetchone()
        assert row is None
    finally:
        connection.close()


def test_persists_inactive_flag_exactly(tmp_path: Path) -> None:
    db_path = tmp_path / "account-inactive.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    try:
        account = _account(number="1300", is_active=False)
        repository.add(account)

        loaded = repository.get_by_number(account.number)
        assert loaded is not None
        assert loaded.is_active is False
    finally:
        connection.close()


def test_can_read_after_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "account-reopen.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    account = _account("1400")
    try:
        repository.add(account)
    finally:
        connection.close()

    reopened_repository, reopened_connection = _new_repository(db_path)
    try:
        loaded = reopened_repository.get_by_number(account.number)
        assert loaded is not None
        assert loaded.number == account.number
    finally:
        reopened_connection.close()


def test_schema_contains_only_expected_business_tables_for_phase(tmp_path: Path) -> None:
    db_path = tmp_path / "account-schema.db"
    _bootstrap_v3(db_path)

    tables = _table_names(db_path)
    expected = {
        "schema_migrations",
        "journal_entries",
        "journal_entry_lines",
        "accounts",
    }
    assert expected.issubset(tables)

    forbidden = {
        "accounting_periods",
        "year_end_snapshots",
        "opening_entries",
    }
    assert forbidden.isdisjoint(tables)


def test_account_repository_does_not_affect_journal_entry_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "account-journal-isolation.db"
    _bootstrap_v3(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository.add(_account("1500"))
        row = connection.execute("SELECT COUNT(*) FROM journal_entries").fetchone()
        assert row is not None
        assert int(row[0]) == 0
    finally:
        connection.close()