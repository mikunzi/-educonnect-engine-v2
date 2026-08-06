"""Year-end snapshot identifier value object."""

import re
from dataclasses import dataclass

_YEAR_END_SNAPSHOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class YearEndSnapshotId:
    """Immutable identifier for a year-end snapshot."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("year-end snapshot id must not be empty")
        if self.value != self.value.strip():
            raise ValueError("year-end snapshot id must not have surrounding spaces")
        if len(self.value) > 64:
            raise ValueError("year-end snapshot id must not exceed 64 characters")
        if _YEAR_END_SNAPSHOT_ID_PATTERN.fullmatch(self.value) is None:
            raise ValueError("year-end snapshot id contains invalid characters")
