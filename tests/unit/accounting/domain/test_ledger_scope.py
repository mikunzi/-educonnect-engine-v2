"""Unit tests for LedgerScope value object."""

from dataclasses import FrozenInstanceError

import pytest

from educonnect_engine.accounting.domain.ledger_scope import LedgerScope
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


def test_ledger_scope_holds_explicit_scope_dimensions() -> None:
    scope = LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )

    assert scope.legal_entity_id == LegalEntityId(value="entity-01")
    assert scope.fiscal_year == FiscalYear(value=2026)
    assert scope.currency == Currency(code="CHF")


def test_ledger_scope_is_frozen_and_uses_slots() -> None:
    scope = LedgerScope(
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        currency=Currency(code="CHF"),
    )

    with pytest.raises(FrozenInstanceError):
        type(scope).__setattr__(scope, "currency", Currency(code="EUR"))

    assert not hasattr(scope, "__dict__")
