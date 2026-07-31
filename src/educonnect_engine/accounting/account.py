"""Accounting account entity."""

from dataclasses import dataclass

from .enums import AccountCategory, FinancialStatement, NormalBalance


@dataclass(frozen=True, slots=True)
class Account:
    """Immutable account structure with basic integrity checks."""

    number: int
    name: str
    category: AccountCategory
    class_number: int
    group_number: int
    normal_balance: NormalBalance
    statement: FinancialStatement
    description: str = ""
    purpose: str = ""
    reconcilable: bool = False
    cash_account: bool = False

    def __post_init__(self) -> None:
        """Validate basic structural constraints."""
        if self.number <= 0:
            raise ValueError("number must be positive")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.class_number <= 0:
            raise ValueError("class_number must be positive")
        if self.group_number <= 0:
            raise ValueError("group_number must be positive")
