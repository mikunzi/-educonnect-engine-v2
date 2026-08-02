"""Closing timestamp value object."""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ClosingTimestamp:
    """Immutable UTC closing timestamp with explicit timezone requirement."""

    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None:
            raise ValueError("closing timestamp must be timezone-aware")
        if self.value.tzinfo is not UTC:
            raise ValueError("closing timestamp timezone must be UTC")
