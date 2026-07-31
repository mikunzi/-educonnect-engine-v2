"""Core shared type aliases and protocol contracts."""

from typing import NewType, Protocol

EntityId = NewType("EntityId", str)
CurrencyCode = NewType("CurrencyCode", str)
UserId = NewType("UserId", str)


class Serializable(Protocol):
    """Protocol for objects that can expose a serializable payload."""

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation."""
