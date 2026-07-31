"""Accounting domain entities.

These are structural scaffolds only. No business rules are implemented.
"""

from dataclasses import dataclass
from datetime import date

from educonnect_engine.core.money import Money
from educonnect_engine.core.types import EntityId


@dataclass(frozen=True, slots=True)
class JournalLine:
	"""Single accounting line in a journal entry."""

	id: EntityId
	ledger_account_id: EntityId
	amount: Money
	description: str

	def __post_init__(self) -> None:
		"""Validate base structural invariants for a journal line."""
		if not str(self.id).strip():
			raise ValueError("id must not be empty")
		if not str(self.ledger_account_id).strip():
			raise ValueError("ledger_account_id must not be empty")
		if not isinstance(self.amount, Money):
			raise TypeError("amount must be an instance of Money")
		if not self.description.strip():
			raise ValueError("description must not be empty")


@dataclass(frozen=True, slots=True)
class JournalEntry:
	"""Journal entry header with associated lines."""

	id: EntityId
	reference: str
	posting_date: date
	lines: tuple[JournalLine, ...]


@dataclass(frozen=True, slots=True)
class LedgerAccount:
	"""Ledger view model for a single account."""

	id: EntityId
	code: str
	name: str
	opening_balance: Money
	closing_balance: Money


@dataclass(frozen=True, slots=True)
class Ledger:
	"""Ledger container for a given reporting period."""

	id: EntityId
	period_start: date
	period_end: date
	accounts: tuple[LedgerAccount, ...]


@dataclass(frozen=True, slots=True)
class TrialBalance:
	"""Trial balance snapshot scaffold for a given date."""

	id: EntityId
	as_of: date
	total_debit: Money
	total_credit: Money
	accounts: tuple[LedgerAccount, ...]


@dataclass(frozen=True, slots=True)
class BalanceSheet:
	"""Balance sheet structure scaffold."""

	id: EntityId
	as_of: date
	assets_total: Money
	liabilities_total: Money
	equity_total: Money


@dataclass(frozen=True, slots=True)
class IncomeStatement:
	"""Income statement structure scaffold."""

	id: EntityId
	period_start: date
	period_end: date
	revenue_total: Money
	expense_total: Money
	net_income: Money
