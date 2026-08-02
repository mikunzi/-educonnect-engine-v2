"""Fiscal year value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FiscalYear:
    """Immutable fiscal year within supported range."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 1900:
            raise ValueError("fiscal year must be greater than or equal to 1900")
        if self.value > 9999:
            raise ValueError("fiscal year must be lower than or equal to 9999")
