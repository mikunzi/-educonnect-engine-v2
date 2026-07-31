"""Unit tests for shared error hierarchy."""

from educonnect_engine.shared.errors import DomainError, EduConnectError, ValidationError


def test_error_hierarchy() -> None:
    assert issubclass(ValidationError, EduConnectError)
    assert issubclass(DomainError, EduConnectError)
