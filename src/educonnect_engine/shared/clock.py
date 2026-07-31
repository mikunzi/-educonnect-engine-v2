"""Shared clock primitive."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timezone


@dataclass(frozen=True, slots=True)
class Clock:
    """UTC clock abstraction for deterministic time access points."""

    tz: timezone = UTC

    def now(self) -> datetime:
        """Return current timezone-aware datetime."""
        return datetime.now(tz=self.tz)

    def today(self) -> date:
        """Return current date in configured timezone."""
        return self.now().date()
