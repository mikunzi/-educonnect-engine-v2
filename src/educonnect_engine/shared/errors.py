"""Shared Kernel exception hierarchy."""


class EduConnectError(Exception):
    """Base exception type for project-specific errors."""


class ValidationError(EduConnectError):
    """Raised when a value fails generic validation constraints."""


class DomainError(EduConnectError):
    """Raised when a domain invariant is violated."""
