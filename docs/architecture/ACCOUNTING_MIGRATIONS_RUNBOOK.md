# Accounting SQLite Migrations Runbook

## Purpose

This runbook documents operational steps for SQLite schema migrations in Phase 7.
It applies to the accounting persistence adapter only.

## Scope

- Migration engine: `SQLiteSchemaBootstrap`
- Migration source: `src/educonnect_engine/accounting/infrastructure/sqlite/schema/migrations`
- Version tracking table: `schema_migrations`
- Supported migration versions: `1..4`

This runbook does not define production rollout policies.

## Preconditions

1. Use Python `3.14` environment.
2. Ensure target database path is accessible.
3. Ensure no other process writes to the database during bootstrap.

## Bootstrap Procedure

Use the bootstrap utility from application orchestration code or scripts.

```python
from educonnect_engine.accounting.infrastructure.sqlite.bootstrap import SQLiteSchemaBootstrap
from educonnect_engine.accounting.infrastructure.sqlite.connection import ConnectionFactory, DatabaseConfig

config = DatabaseConfig(path="/absolute/path/to/accounting.db")
bootstrap = SQLiteSchemaBootstrap(
    connection_factory=ConnectionFactory(),
    config=config,
    target_version=4,
)
bootstrap.bootstrap()
```

Behavior:

- opens one connection,
- starts `BEGIN IMMEDIATE`,
- applies pending migrations up to `target_version`,
- records each applied migration in `schema_migrations`,
- commits atomically.

On failure, bootstrap rolls back and re-raises the original exception.

## Verify Current Version

```python
current_version = bootstrap.current_version()
print(current_version)
```

Expected values:

- `0`: schema not initialized,
- `1..4`: initialized up to recorded migration version.

## Idempotency

Running `bootstrap()` multiple times with the same `target_version` is safe.
Already recorded versions are skipped.

## Troubleshooting

- `ValueError("unsupported schema target version")`:
  choose a version declared in `_MIGRATIONS`.
- `sqlite3.IntegrityError` during migration:
  inspect SQL constraints in migration files and database state.
- Locked database errors:
  stop concurrent writers and retry.

## Quality Gates for Migration Changes

Before merging migration-related changes, run:

```bash
ruff check
mypy src
pytest
```
