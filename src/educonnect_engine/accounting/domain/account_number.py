"""Account number value object."""

import re
from dataclasses import dataclass

_ACCOUNT_NUMBER_PATTERN = re.compile(r"^[0-9]{4}$")


@dataclass(frozen=True, slots=True)
class AccountNumber:
    """Immutable accounting account number with V1 format."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("account number must not be empty")
        if _ACCOUNT_NUMBER_PATTERN.fullmatch(self.value) is None:
            raise ValueError("account number must contain exactly 4 digits")
