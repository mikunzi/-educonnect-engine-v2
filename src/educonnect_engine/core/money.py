"""Money primitive for explicit monetary typing.

This module provides data shape only; business rules are intentionally omitted.
"""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.core.types import CurrencyCode


@dataclass(frozen=True, slots=True)
class Money:
    """Currency amount value object scaffold."""

    amount: Decimal
    currency: CurrencyCode
