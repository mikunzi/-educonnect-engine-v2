"""Base entities and value objects for future domain models."""

from dataclasses import dataclass
from typing import Protocol


class DomainEvent(Protocol):
    """Marker protocol for domain events."""


@dataclass(slots=True, kw_only=True)
class Entity:
    """Base entity type to be specialized by each bounded context."""

    id: str
