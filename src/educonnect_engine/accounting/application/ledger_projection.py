"""LedgerProjection use case."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from educonnect_engine.accounting.domain.ledger import Ledger
from educonnect_engine.accounting.domain.ledger_projection_service import LedgerProjectionService
from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.accounting.domain.repositories import (
    LedgerProjectionRepository,
    UnitOfWork,
)
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


class LedgerProjectionUnitOfWork(UnitOfWork, Protocol):
    """UnitOfWork contract required by LedgerProjection handler."""

    @property
    def ledger_projection_repository(self) -> LedgerProjectionRepository:
        """Ledger projection source repository bound to current transaction."""


@dataclass(frozen=True, slots=True)
class LedgerProjectionCommand:
    """Input payload for projecting one ledger scope."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    currency: Currency


@dataclass(frozen=True, slots=True)
class LedgerProjectionResult:
    """Typed output returned by LedgerProjection."""

    scope: LedgerScope
    ledger: Ledger
    journal_entry_count: int
    ledger_line_count: int


@dataclass(frozen=True, slots=True)
class LedgerProjectionHandler:
    """Transactional application service for deterministic ledger projection."""

    uow: LedgerProjectionUnitOfWork
    projection_service: LedgerProjectionService = field(default_factory=LedgerProjectionService)

    def execute(self, command: LedgerProjectionCommand) -> LedgerProjectionResult:
        scope = LedgerScope(
            legal_entity_id=command.legal_entity_id,
            fiscal_year=command.fiscal_year,
            currency=command.currency,
        )

        with self.uow.transaction():
            entries = self.uow.ledger_projection_repository.get_posted_entries(scope)
            ledger = self.projection_service.project(scope=scope, entries=entries)
            return LedgerProjectionResult(
                scope=scope,
                ledger=ledger,
                journal_entry_count=len(entries),
                ledger_line_count=len(ledger.lines()),
            )
