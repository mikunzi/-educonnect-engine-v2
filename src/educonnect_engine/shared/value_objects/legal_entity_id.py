"""Legal entity identifier value object."""

import re
from dataclasses import dataclass

_LEGAL_ENTITY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class LegalEntityId:
    """Immutable legal entity identifier."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("legal entity id must not be empty")
        if self.value != self.value.strip():
            raise ValueError("legal entity id must not have surrounding spaces")
        if len(self.value) > 64:
            raise ValueError("legal entity id must not exceed 64 characters")
        if _LEGAL_ENTITY_ID_PATTERN.fullmatch(self.value) is None:
            raise ValueError("legal entity id contains invalid characters")
