"""Account entity for chart-of-accounts persistence."""

from __future__ import annotations

from dataclasses import dataclass

from .account_category import AccountCategory
from .account_classification import AccountClassification
from .account_number import AccountNumber


@dataclass(frozen=True, slots=True)
class Account:
    """Immutable accounting account metadata."""

    number: AccountNumber
    name: str
    category: AccountCategory
    classification: AccountClassification
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("account name must not be empty")