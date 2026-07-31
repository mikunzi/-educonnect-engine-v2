"""Core exception hierarchy for EduConnect Engine."""


class EduConnectError(Exception):
    """Base exception type for all project-specific errors."""


class ValidationError(EduConnectError):
    """Raised when a value fails validation rules."""


class ConfigurationError(EduConnectError):
    """Raised when runtime or environment configuration is invalid."""
