"""Explicit mapping between Account domain objects and SQLite rows."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from educonnect_engine.accounting.domain.account import Account
from educonnect_engine.accounting.domain.account_category import AccountCategory
from educonnect_engine.accounting.domain.account_classification import AccountClassification
from educonnect_engine.accounting.domain.account_number import AccountNumber


@dataclass(frozen=True, slots=True)
class AccountRow:
    """SQLite row payload for one account."""

    account_number: str
    name: str
    category: str
    classification: str
    is_active: int


class AccountSQLiteMapper:
    """Map Account entities to and from SQLite row structures."""

    def to_row(self, account: Account) -> AccountRow:
        return AccountRow(
            account_number=account.number.value,
            name=account.name,
            category=account.category.value,
            classification=account.classification.value,
            is_active=1 if account.is_active else 0,
        )

    def from_row(self, row: sqlite3.Row) -> Account:
        is_active_value = int(row["is_active"])
        if is_active_value not in (0, 1):
            raise ValueError("invalid account is_active value")

        return Account(
            number=AccountNumber(value=str(row["account_number"])),
            name=str(row["name"]),
            category=AccountCategory(str(row["category"])),
            classification=AccountClassification(str(row["classification"])),
            is_active=bool(is_active_value),
        )