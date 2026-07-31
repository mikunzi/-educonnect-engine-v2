"""Core service contracts."""

from typing import Protocol


class UnitOfWork(Protocol):
    """Unit of work boundary contract for transactional coordination."""

    def commit(self) -> None:
        """Persist staged changes."""

    def rollback(self) -> None:
        """Discard staged changes."""
