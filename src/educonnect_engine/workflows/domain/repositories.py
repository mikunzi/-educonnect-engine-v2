"""Workflows repository ports scaffold."""

from typing import Protocol


class WorkflowsRepository(Protocol):
    """Repository contract for workflow persistence adapters."""
