"""Integration tests for SQLiteAccountingPeriodRepository."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from educonnect_engine.accounting.domain.accounting_period import AccountingPeriod
from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId
from educonnect_engine.accounting.domain.accounting_period_status import AccountingPeriodStatus
from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import (
    ConnectionFactory,
    DatabaseConfig,
)
from educonnect_engine.accounting.infrastructure.sqlite.mappers.accounting_period_mapper import (
    AccountingPeriodRow,
    AccountingPeriodSQLiteMapper,
)
from educonnect_engine.accounting.infrastructure.sqlite.repositories import (
    SQLiteAccountingPeriodRepository,
)
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class _FailingPeriodMapper(AccountingPeriodSQLiteMapper):
    def to_row(self, period: AccountingPeriod) -> AccountingPeriodRow:
        row = super().to_row(period)
        return AccountingPeriodRow(
            id="",
            legal_entity_id=row.legal_entity_id,
            fiscal_year=row.fiscal_year,
            start_date=row.start_date,
            end_date=row.end_date,
            status=row.status,
            version=row.version,
        )


def _period(
    period_id: str = "PER-2026-01",
    *,
    legal_entity_id: str = "entity-01",
    fiscal_year: int = 2026,
    start_date: date = date(2026, 1, 1),
    end_date: date = date(2026, 1, 31),
    status: AccountingPeriodStatus = AccountingPeriodStatus.OPEN,
    version: int = 0,
) -> AccountingPeriod:
    return AccountingPeriod(
        id=AccountingPeriodId(value=period_id),
        legal_entity_id=LegalEntityId(value=legal_entity_id),
        fiscal_year=FiscalYear(value=fiscal_year),
        start_date=start_date,
        end_date=end_date,
        status=status,
        version=version,
    )


def _bootstrap_v4(db_path: Path) -> None:
    bootstrap = SQLiteSchemaBootstrap(
        connection_factory=ConnectionFactory(),
        config=DatabaseConfig(path=str(db_path)),
        target_version=4,
    )
    bootstrap.bootstrap()


def _new_repository(
    db_path: Path,
) -> tuple[SQLiteAccountingPeriodRepository, sqlite3.Connection]:
    manager = ConnectionFactory.create(DatabaseConfig(path=str(db_path)))
    connection = manager.open()
    repository = SQLiteAccountingPeriodRepository(connection=connection)
    return repository, connection


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(str(db_path)) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        ).fetchall()
    return {str(row[0]) for row in rows}


def test_add_and_get_by_id_round_trip_preserves_period_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "period.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        period = _period()
        repository.add(period)

        loaded = repository.get_by_id(period.id)
        assert loaded is not None
        assert isinstance(loaded, AccountingPeriod)
        assert loaded.id == period.id
        assert loaded.legal_entity_id == period.legal_entity_id
        assert loaded.fiscal_year == period.fiscal_year
        assert loaded.start_date == period.start_date
        assert loaded.end_date == period.end_date
        assert loaded.status is period.status
        assert loaded.version == period.version
    finally:
        connection.close()


def test_get_by_id_unknown_returns_none(tmp_path: Path) -> None:
    db_path = tmp_path / "period-unknown.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        missing = repository.get_by_id(AccountingPeriodId(value="PER-MISSING"))
        assert missing is None
    finally:
        connection.close()


def test_add_duplicate_raises_error(tmp_path: Path) -> None:
    db_path = tmp_path / "period-duplicate.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        period = _period()
        repository.add(period)

        try:
            repository.add(period)
        except ValueError as exc:
            assert "already exists" in str(exc)
        else:
            raise AssertionError("expected duplicate accounting period error")
    finally:
        connection.close()


def test_add_uses_atomic_savepoint_and_rolls_back_on_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "period-rollback.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository._mapper = _FailingPeriodMapper()  # type: ignore[attr-defined]
        period = _period("PER-2026-ROLLBACK")

        try:
            repository.add(period)
        except ValueError:
            pass
        else:
            raise AssertionError("expected insertion failure")

        row = connection.execute(
            "SELECT 1 FROM accounting_periods WHERE id = ?",
            (period.id.value,),
        ).fetchone()
        assert row is None
    finally:
        connection.close()


def test_save_persists_status_and_version_without_automatic_transition(tmp_path: Path) -> None:
    db_path = tmp_path / "period-save.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        open_period = _period()
        repository.add(open_period)

        closed_period = _period(
            status=AccountingPeriodStatus.CLOSED,
            version=1,
        )
        repository.save(closed_period, expected_version=0)

        loaded = repository.get_by_id(open_period.id)
        assert loaded is not None
        assert loaded.status is AccountingPeriodStatus.CLOSED
        assert loaded.version == 1
    finally:
        connection.close()


def test_save_rejects_expected_version_mismatch(tmp_path: Path) -> None:
    db_path = tmp_path / "period-version-mismatch.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        period = _period()
        repository.add(period)

        updated = _period(status=AccountingPeriodStatus.CLOSED, version=1)
        try:
            repository.save(updated, expected_version=2)
        except ValueError as exc:
            assert "version mismatch" in str(exc)
        else:
            raise AssertionError("expected version mismatch error")
    finally:
        connection.close()


def test_is_open_matches_scope_status_and_date(tmp_path: Path) -> None:
    db_path = tmp_path / "period-is-open.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository.add(_period())
        assert repository.is_open(
            LegalEntityId(value="entity-01"),
            FiscalYear(value=2026),
            date(2026, 1, 15),
        )
        assert not repository.is_open(
            LegalEntityId(value="entity-01"),
            FiscalYear(value=2026),
            date(2026, 2, 1),
        )

        repository.save(
            _period(status=AccountingPeriodStatus.CLOSED, version=1),
            expected_version=0,
        )
        assert not repository.is_open(
            LegalEntityId(value="entity-01"),
            FiscalYear(value=2026),
            date(2026, 1, 15),
        )
    finally:
        connection.close()


def test_has_open_period_and_has_overlapping_period_behave_as_expected(tmp_path: Path) -> None:
    db_path = tmp_path / "period-overlap.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository.add(_period())
        assert repository.has_open_period(LegalEntityId(value="entity-01"), FiscalYear(value=2026))
        assert repository.has_overlapping_period(
            LegalEntityId(value="entity-01"),
            FiscalYear(value=2026),
            date(2026, 1, 15),
            date(2026, 2, 15),
        )
        assert not repository.has_overlapping_period(
            LegalEntityId(value="entity-01"),
            FiscalYear(value=2026),
            date(2026, 2, 1),
            date(2026, 2, 28),
        )
    finally:
        connection.close()


def test_dates_are_stored_as_iso_8601_strings(tmp_path: Path) -> None:
    db_path = tmp_path / "period-date-format.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        period = _period(start_date=date(2026, 3, 1), end_date=date(2026, 3, 31))
        repository.add(period)

        row = connection.execute(
            "SELECT start_date, end_date FROM accounting_periods WHERE id = ?",
            (period.id.value,),
        ).fetchone()
        assert row is not None
        assert str(row["start_date"]) == "2026-03-01"
        assert str(row["end_date"]) == "2026-03-31"
    finally:
        connection.close()


def test_can_read_after_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "period-reopen.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    period = _period("PER-2026-REOPEN")
    try:
        repository.add(period)
    finally:
        connection.close()

    reopened_repository, reopened_connection = _new_repository(db_path)
    try:
        loaded = reopened_repository.get_by_id(period.id)
        assert loaded is not None
        assert loaded.id == period.id
    finally:
        reopened_connection.close()


def test_schema_contains_expected_tables_and_no_future_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "period-schema.db"
    _bootstrap_v4(db_path)

    tables = _table_names(db_path)
    expected = {
        "schema_migrations",
        "journal_entries",
        "journal_entry_lines",
        "accounts",
        "accounting_periods",
    }
    assert expected.issubset(tables)

    forbidden = {
        "fiscal_year_closings",
        "year_end_snapshots",
        "opening_entries",
    }
    assert forbidden.isdisjoint(tables)


def test_period_repository_does_not_affect_account_or_journal_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "period-isolation.db"
    _bootstrap_v4(db_path)
    repository, connection = _new_repository(db_path)

    try:
        repository.add(_period("PER-2026-ISOLATION"))
        account_count = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()
        journal_count = connection.execute("SELECT COUNT(*) FROM journal_entries").fetchone()

        assert account_count is not None
        assert journal_count is not None
        assert int(account_count[0]) == 0
        assert int(journal_count[0]) == 0
    finally:
        connection.close()