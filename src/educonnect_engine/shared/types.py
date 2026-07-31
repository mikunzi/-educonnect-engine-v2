"""Shared Kernel type aliases."""

from collections.abc import Callable
from datetime import date, datetime

type DateProvider = Callable[[], date]
type DateTimeProvider = Callable[[], datetime]
type ErrorMessage = str
