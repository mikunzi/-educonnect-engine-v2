"""Idempotency key value object."""

import re
from dataclasses import dataclass

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Immutable key identifying a command execution attempt."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("idempotency key must not be empty")
        if self.value != self.value.strip():
            raise ValueError("idempotency key must not have surrounding spaces")
        if len(self.value) > 128:
            raise ValueError("idempotency key must not exceed 128 characters")
        if _IDEMPOTENCY_KEY_PATTERN.fullmatch(self.value) is None:
            raise ValueError(
                "idempotency key must contain only letters, digits, '.', '_', ':' or '-'",
            )
