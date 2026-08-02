# EduConnect Engine v2

Python 3.14 codebase for a modular accounting core using Clean Architecture + DDD.

This repository is no longer scaffold-only: the accounting core is implemented through Phase 6.2
and stabilized as an architecture milestone before Phase 6.3.

## Stack

- Python 3.14
- src layout (`src/educonnect_engine`)
- pytest
- ruff
- mypy
- pre-commit
- GitHub Actions
- Makefile

## Architecture Principles

- Clean Architecture
- SOLID
- Domain-Driven Design (bounded contexts)
- Full type hints

Bounded contexts currently included:

- accounting
- finance
- tax
- reporting
- ai
- companies
- documents
- pedagogy
- workflows

Shared platform layers:

- core
- shared

Every context follows:

- domain
- application
- infrastructure
- presentation

## Repository Layout

```text
src/
	educonnect_engine/
		accounting/
		finance/
		tax/
		reporting/
		ai/
		companies/
		documents/
		pedagogy/
		workflows/
		core/
		shared/
tests/
docs/
prompts/
examples/
```

## Quick Start

```bash
python3.14 -m venv .venv
source .venv/bin/activate
make install-dev
make check
```

## Current Accounting Milestone (Post-Phase 6.2)

Completed phases:

- Shared Kernel
- JournalEntry / JournalLine
- RecordJournalEntry
- PostJournalEntry
- ReverseJournalEntry
- Ledger Projection
- Trial Balance Projection
- Balance Sheet Projection
- Income Statement Projection
- Financial Statements Projection
- Accounting Period Lifecycle
- Fiscal Year Closing

Next phase:

- Phase 6.3 - Closing Entries & Opening Entries

## Accounting Processing Chain

- Record a balanced JournalEntry (RECORDED)
- Post entry when period is OPEN (RECORDED -> POSTED)
- Reverse posted entry through traceable correction flow
- Project deterministic Ledger from POSTED entries
- Project Trial Balance from Ledger
- Project Balance Sheet and Income Statement
- Assemble Financial Statements with consistency checks
- Manage period lifecycle (OPEN -> CLOSED -> LOCKED)
- Close fiscal year (OPEN -> CLOSED) with explicit prerequisites

## Major Invariants

- Double-entry balance enforced for journal entries
- Single-currency journal entry lines
- UTC timezone enforcement for posting/closing timestamps
- Immutable value objects and aggregates (`dataclass(frozen=True, slots=True)`)
- Idempotency on command use cases
- Optimistic version checks on lifecycle transitions
- Financial statements coherence between balance sheet and income statement

## Quality Snapshot (2026-08-02)

- Ruff: pass
- MyPy: pass (`151` source files)
- Pytest: pass (`379` tests)
- Global coverage: `97%`
