# Contributing Guide

Thank you for contributing to EduConnect Engine v2.

## Prerequisites

- Python 3.14
- Git

## Local Setup

```bash
python3.14 -m venv .venv
source .venv/bin/activate
make install-dev
```

## Development Workflow

1. Create a feature branch from `main`.
2. Keep changes scoped to one concern.
3. Add or update tests.
4. Run local quality checks.

```bash
make format
make lint
make typecheck
make test
```

Or run all checks:

```bash
make check
```

## Architecture Rules

- Respect clean architecture boundaries.
- Domain layer must not depend on infrastructure.
- Depend on interfaces/protocols, not concrete implementations.
- Keep modules cohesive and single-purpose.
- Preserve full type hints.

## Commit and PR Expectations

- Write clear commit messages.
- Open PRs with rationale, impact, and testing notes.
- Ensure CI passes before merge.

## Scope Reminder

This repository is currently scaffold-only. Do not add business logic unless explicitly planned.
