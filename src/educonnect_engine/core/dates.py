"""Date and period primitives for the platform core."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class DateRange:
    """Inclusive date range scaffold."""

    start: date
    end: date
