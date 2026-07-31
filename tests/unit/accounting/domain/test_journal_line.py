"""Unit tests for JournalLine entity."""

from decimal import Decimal

import pytest

from educonnect_engine.accounting.domain import JournalLine
from educonnect_engine.core.money import Money
from educonnect_engine.core.types import CurrencyCode, EntityId


def test_journal_line_creation_success() -> None:
    line = JournalLine(
        id=EntityId("jl-1"),
        ledger_account_id=EntityId("acc-1000"),
        amount=Money(amount=Decimal("10.00"), currency=CurrencyCode("CHF")),
        description="Tuition invoice",
    )

    assert line.id == EntityId("jl-1")
    assert line.ledger_account_id == EntityId("acc-1000")
    assert line.amount.amount == Decimal("10.00")
    assert line.amount.currency == CurrencyCode("CHF")
    assert line.description == "Tuition invoice"


@pytest.mark.parametrize(
    ("id_value", "ledger_account_id", "description"),
    [
        (EntityId(""), EntityId("acc-1"), "desc"),
        (EntityId("jl-1"), EntityId(""), "desc"),
        (EntityId("jl-1"), EntityId("acc-1"), "   "),
    ],
)
def test_journal_line_rejects_empty_required_text_fields(
    id_value: EntityId,
    ledger_account_id: EntityId,
    description: str,
) -> None:
    with pytest.raises(ValueError):
        JournalLine(
            id=id_value,
            ledger_account_id=ledger_account_id,
            amount=Money(amount=Decimal("1.00"), currency=CurrencyCode("CHF")),
            description=description,
        )


def test_journal_line_rejects_invalid_amount_type() -> None:
    with pytest.raises(TypeError):
        JournalLine(
            id=EntityId("jl-1"),
            ledger_account_id=EntityId("acc-1"),
            amount="10.00",  # type: ignore[arg-type]
            description="desc",
        )
