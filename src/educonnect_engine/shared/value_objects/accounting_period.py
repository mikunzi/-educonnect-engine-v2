"""Accounting period value object."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class AccountingPeriod:
    """Immutable inclusive accounting period."""

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("accounting period start_date must be before or equal to end_date")

    def contains(self, value: date) -> bool:
        """Return True when date belongs to the inclusive period."""
        return self.start_date <= value <= self.end_date
