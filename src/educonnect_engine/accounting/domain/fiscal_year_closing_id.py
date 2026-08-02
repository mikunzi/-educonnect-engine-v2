"""Fiscal year closing identifier value object."""

import re
from dataclasses import dataclass

_FISCAL_YEAR_CLOSING_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class FiscalYearClosingId:
    """Immutable identifier for a fiscal year closing aggregate."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("fiscal year closing id must not be empty")
        if self.value != self.value.strip():
            raise ValueError("fiscal year closing id must not have surrounding spaces")
        if len(self.value) > 64:
            raise ValueError("fiscal year closing id must not exceed 64 characters")
        if _FISCAL_YEAR_CLOSING_ID_PATTERN.fullmatch(self.value) is None:
            raise ValueError("fiscal year closing id contains invalid characters")
