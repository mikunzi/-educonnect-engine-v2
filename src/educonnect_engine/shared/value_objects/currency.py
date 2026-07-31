"""Currency value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Currency:
    """Immutable 3-letter uppercase currency code."""

    code: str

    def __post_init__(self) -> None:
        if len(self.code) != 3 or not self.code.isalpha():
            raise ValueError("currency code must contain exactly 3 letters")
        if self.code != self.code.upper():
            raise ValueError("currency code must be uppercase")
