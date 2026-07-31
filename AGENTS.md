# AGENTS

This document defines expected behavior for human and AI contributors.

## Purpose

Keep the repository production-ready, modular, and architecture-safe while implementation is staged.

## Operating Rules

- Follow Clean Architecture boundaries.
- Follow SOLID principles.
- Preserve DDD bounded contexts.
- Require full type annotations for new Python code.
- Avoid introducing business logic in scaffold-only phases.

## Code Generation Rules

- Prefer small focused files.
- Do not couple bounded contexts directly.
- Add tests with any executable behavior.
- Keep configs deterministic and CI-friendly.

## Quality Gates

- `ruff check` must pass.
- `mypy` must pass.
- `pytest` must pass.
- pre-commit hooks must pass.

## Safety

- No secrets in source control.
- No hard-coded credentials.
- No destructive repository rewrites without explicit approval.
