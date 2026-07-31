# EduConnect Engine v2

Production-ready Python 3.14 repository skeleton for a modular and scalable engine.

This repository intentionally excludes business implementation and contains only architecture,
tooling, and developer workflow foundations.

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

## Important Note

No business rules, workflows, or external integrations have been implemented yet.
All modules are scaffolds to support iterative delivery.
