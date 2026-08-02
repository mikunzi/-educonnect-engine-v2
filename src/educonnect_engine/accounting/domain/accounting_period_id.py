"""Accounting period identifier value object."""

import re
from dataclasses import dataclass

_ACCOUNTING_PERIOD_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class AccountingPeriodId:
    """Immutable identifier for an accounting period aggregate."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("accounting period id must not be empty")
        if self.value != self.value.strip():
            raise ValueError("accounting period id must not have surrounding spaces")
        if len(self.value) > 64:
            raise ValueError("accounting period id must not exceed 64 characters")
        if _ACCOUNTING_PERIOD_ID_PATTERN.fullmatch(self.value) is None:
            raise ValueError("accounting period id contains invalid characters")
