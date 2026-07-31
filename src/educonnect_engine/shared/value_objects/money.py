"""Money value object."""

from dataclasses import dataclass
from decimal import Decimal

from .currency import Currency


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary amount and currency."""

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not self.amount.is_finite():
            raise ValueError("money amount must be finite")
