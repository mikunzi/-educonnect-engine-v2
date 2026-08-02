"""Ledger scope value object."""

from dataclasses import dataclass

from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


@dataclass(frozen=True, slots=True)
class LedgerScope:
    """Explicit projection scope for a ledger."""

    legal_entity_id: LegalEntityId
    fiscal_year: FiscalYear
    currency: Currency
