"""Percentage value object."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Percentage:
    """Immutable percentage in range [0, 100]."""

    value: Decimal

    def __post_init__(self) -> None:
        if not self.value.is_finite():
            raise ValueError("percentage must be finite")
        if self.value < Decimal("0") or self.value > Decimal("100"):
            raise ValueError("percentage must be between 0 and 100")
