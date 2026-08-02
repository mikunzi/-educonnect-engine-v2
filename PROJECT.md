# PROJECT

## Vision

EduConnect Engine v2 is a modular Python platform that will host financial and AI-driven
capabilities for education-related workflows.

## Current State (Architecture Milestone After Phase 6.2)

- Accounting core implemented and validated through Phase 6.2
- Core architecture stabilized before Phase 6.3
- Tooling baseline preserved (ruff, mypy, pytest, pre-commit, CI)

Completed accounting phases:

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

## Bounded Contexts

- accounting
- finance
- tax
- reporting
- ai
- companies
- documents
- pedagogy
- workflows

## Platform Modules

- core: technical orchestration and shared platform services
- shared: cross-context abstractions and primitives

## Engineering Standards

- Python 3.14 only
- Full type hints
- Clean Architecture and SOLID
- DDD where appropriate
- CI-enforced lint, type, and tests

## Non-Goals (Current Phase)

- SQL/ORM adapter implementation
- HTTP/API runtime layer
- Event bus integration
- Multi-entity consolidation
- Advanced tax automation

## Reference Quality State (2026-08-02)

- Ruff: pass
- MyPy: pass
- Pytest: `379 passed`
- Coverage: `97%`

## Known Technical Debt

- Legacy account scaffold still present in [src/educonnect_engine/accounting/account.py](src/educonnect_engine/accounting/account.py) and its enum companions for compatibility tests.
- Legacy scaffold placeholder still present in [src/educonnect_engine/accounting/domain/entities.py](src/educonnect_engine/accounting/domain/entities.py), intentionally reduced to a deprecation note.
- Public exports in [src/educonnect_engine/accounting/domain/__init__.py](src/educonnect_engine/accounting/domain/__init__.py) are broad and may need tightening when external API boundaries are formalized.
