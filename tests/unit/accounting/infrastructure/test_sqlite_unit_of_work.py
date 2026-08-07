"""Unit tests for SQLiteUnitOfWork."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from educonnect_engine.accounting.infrastructure.sqlite.connection import DatabaseConfig
from educonnect_engine.accounting.infrastructure.sqlite.unit_of_work import SQLiteUnitOfWork


@dataclass
class _FakeRepository:
    connection: object


class _FakeConnection:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.fail_commit = False

    def execute(self, sql: str, _params: object | None = None) -> object:
        self.executed_sql.append(sql)
        return object()

    def commit(self) -> None:
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollback_calls += 1


class _FakeManager:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection
        self.open_calls = 0
        self.close_calls = 0

    def open(self) -> _FakeConnection:
        self.open_calls += 1
        return self._connection

    def close(self) -> None:
        self.close_calls += 1


class _FakeConnectionFactory:
    def __init__(self, manager: _FakeManager) -> None:
        self._manager = manager
        self.calls: list[DatabaseConfig] = []

    def create(self, config: DatabaseConfig) -> _FakeManager:
        self.calls.append(config)
        return self._manager


def _builder(registry: list[_FakeRepository]) -> Callable[[object], _FakeRepository]:
    def build(connection: object) -> _FakeRepository:
        repo = _FakeRepository(connection=connection)
        registry.append(repo)
        return repo

    return build


def _new_uow(
    connection: _FakeConnection,
) -> tuple[SQLiteUnitOfWork, _FakeManager, _FakeConnectionFactory]:
    manager = _FakeManager(connection)
    factory = _FakeConnectionFactory(manager)
    config = DatabaseConfig(path=":memory:")
    account_repos: list[_FakeRepository] = []
    period_repos: list[_FakeRepository] = []
    journal_repos: list[_FakeRepository] = []
    ledger_projection_repos: list[_FakeRepository] = []
    uow = SQLiteUnitOfWork(
        connection_factory=factory,
        config=config,
        account_repository_builder=_builder(account_repos),
        accounting_period_repository_builder=_builder(period_repos),
        journal_entry_repository_builder=_builder(journal_repos),
        ledger_projection_repository_builder=_builder(ledger_projection_repos),
    )
    return uow, manager, factory


def _open_nested_transaction(uow: SQLiteUnitOfWork) -> None:
    with uow.transaction():
        pass


def test_transaction_success_calls_begin_commit_and_close() -> None:
    connection = _FakeConnection()
    uow, manager, _factory = _new_uow(connection)

    with uow.transaction():
        pass

    assert connection.executed_sql == ["BEGIN"]
    assert connection.commit_calls == 1
    assert connection.rollback_calls == 0
    assert manager.open_calls == 1
    assert manager.close_calls == 1


def test_transaction_error_calls_rollback_and_close_then_reraises() -> None:
    connection = _FakeConnection()
    uow, manager, _factory = _new_uow(connection)

    with pytest.raises(ValueError, match="boom"), uow.transaction():
        raise ValueError("boom")

    assert connection.commit_calls == 0
    assert connection.rollback_calls == 1
    assert manager.close_calls == 1


def test_commit_failure_triggers_rollback_and_closes_connection() -> None:
    connection = _FakeConnection()
    connection.fail_commit = True
    uow, manager, _factory = _new_uow(connection)

    with pytest.raises(RuntimeError, match="commit failed"), uow.transaction():
        pass

    assert connection.commit_calls == 1
    assert connection.rollback_calls == 1
    assert manager.close_calls == 1


def test_repositories_share_exact_same_connection_in_transaction() -> None:
    connection = _FakeConnection()
    uow, _manager, _factory = _new_uow(connection)

    with uow.transaction():
        account_repo = uow.account_repository
        period_repo = uow.accounting_period_repository
        journal_repo = uow.journal_entry_repository
        ledger_projection_repo = uow.ledger_projection_repository

        assert account_repo.connection is connection
        assert period_repo.connection is connection
        assert journal_repo.connection is connection
        assert ledger_projection_repo.connection is connection


def test_repositories_are_unavailable_outside_transaction() -> None:
    connection = _FakeConnection()
    uow, _manager, _factory = _new_uow(connection)

    with pytest.raises(RuntimeError, match="transaction is not active"):
        _ = uow.account_repository

    with pytest.raises(RuntimeError, match="transaction is not active"):
        _ = uow.ledger_projection_repository


def test_nested_transaction_is_rejected() -> None:
    connection = _FakeConnection()
    uow, _manager, _factory = _new_uow(connection)

    with uow.transaction(), pytest.raises(RuntimeError, match="transaction already active"):
        _open_nested_transaction(uow)


def test_commit_and_rollback_methods_require_active_transaction() -> None:
    connection = _FakeConnection()
    uow, _manager, _factory = _new_uow(connection)

    with pytest.raises(RuntimeError, match="transaction is not active"):
        uow.commit()

    with pytest.raises(RuntimeError, match="transaction is not active"):
        uow.rollback()


def test_close_is_idempotent_outside_transaction() -> None:
    connection = _FakeConnection()
    uow, manager, _factory = _new_uow(connection)

    uow.close()
    uow.close()

    assert manager.close_calls == 0