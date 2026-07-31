"""Use-case abstractions used by bounded contexts."""

from typing import Protocol, TypeVar

RequestT = TypeVar("RequestT", contravariant=True)
ResponseT = TypeVar("ResponseT", covariant=True)


class UseCase(Protocol[RequestT, ResponseT]):
    """Contract for application services."""

    def __call__(self, request: RequestT) -> ResponseT:
        """Execute use case."""
