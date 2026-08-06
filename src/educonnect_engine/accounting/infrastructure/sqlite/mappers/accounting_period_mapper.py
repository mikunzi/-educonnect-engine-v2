"""Explicit mapping between AccountingPeriod domain objects and SQLite rows."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from educonnect_engine.accounting.domain.accounting_period import AccountingPeriod
from educonnect_engine.accounting.domain.accounting_period_id import AccountingPeriodId
from educonnect_engine.accounting.domain.accounting_period_status import AccountingPeriodStatus
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId


@dataclass(frozen=True, slots=True)
class AccountingPeriodRow:
    """SQLite row payload for one accounting period."""

    id: str
    legal_entity_id: str
    fiscal_year: int
    start_date: str
    end_date: str
    status: str
    version: int


class AccountingPeriodSQLiteMapper:
    """Map AccountingPeriod aggregates to and from SQLite row structures."""

    def to_row(self, period: AccountingPeriod) -> AccountingPeriodRow:
        return AccountingPeriodRow(
            id=period.id.value,
            legal_entity_id=period.legal_entity_id.value,
            fiscal_year=period.fiscal_year.value,
            start_date=period.start_date.isoformat(),
            end_date=period.end_date.isoformat(),
            status=period.status.value,
            version=period.version,
        )

    def from_row(self, row: sqlite3.Row) -> AccountingPeriod:
        return AccountingPeriod(
            id=AccountingPeriodId(value=str(row["id"])),
            legal_entity_id=LegalEntityId(value=str(row["legal_entity_id"])),
            fiscal_year=FiscalYear(value=int(row["fiscal_year"])),
            start_date=date.fromisoformat(str(row["start_date"])),
            end_date=date.fromisoformat(str(row["end_date"])),
            status=AccountingPeriodStatus(str(row["status"])),
            version=int(row["version"]),
        )