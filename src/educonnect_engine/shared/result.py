"""Shared result type for explicit success/failure flows."""

from dataclasses import dataclass
from typing import TypeVar

ValueT = TypeVar("ValueT")
ErrorT = TypeVar("ErrorT")


@dataclass(frozen=True, slots=True)
class Result[ValueT, ErrorT]:
    """Discriminated result with exactly one branch set."""

    _value: ValueT | None = None
    _error: ErrorT | None = None

    def __post_init__(self) -> None:
        if (self._value is None) == (self._error is None):
            raise ValueError("result must contain either value or error")

    @property
    def is_ok(self) -> bool:
        return self._error is None

    @property
    def is_err(self) -> bool:
        return self._value is None

    @property
    def value(self) -> ValueT:
        if self._value is None:
            raise ValueError("result does not contain a value")
        return self._value

    @property
    def error(self) -> ErrorT:
        if self._error is None:
            raise ValueError("result does not contain an error")
        return self._error

    @classmethod
    def ok(cls, value: ValueT) -> Result[ValueT, ErrorT]:
        return cls(_value=value)

    @classmethod
    def err(cls, error: ErrorT) -> Result[ValueT, ErrorT]:
        return cls(_error=error)
