"""Ledger projection service."""

from dataclasses import dataclass

from .journal_entry import JournalEntry
from .journal_entry_status import JournalEntryStatus
from .ledger import Ledger
from .ledger_account import LedgerAccount
from .ledger_line import LedgerLine
from .ledger_scope import LedgerScope


class UnpostedJournalEntryProjectionError(Exception):
    """Raised when ledger projection receives a non-posted journal entry."""


class LedgerScopeMismatchError(Exception):
    """Raised when journal entries do not match ledger scope dimensions."""


class LedgerCurrencyMismatchError(Exception):
    """Raised when journal entries use a currency different from ledger scope."""


@dataclass(frozen=True, slots=True)
class LedgerProjectionService:
    """Project deterministic ledger views from posted journal entries only."""

    def project(self, *, scope: LedgerScope, entries: tuple[JournalEntry, ...]) -> Ledger:
        projected_lines: list[LedgerLine] = []

        for entry in entries:
            if entry.status is not JournalEntryStatus.POSTED:
                raise UnpostedJournalEntryProjectionError(
                    "ledger projection accepts POSTED journal entries only",
                )
            if entry.posted_at is None:
                raise UnpostedJournalEntryProjectionError(
                    "posted journal entry must define posted_at",
                )
            if entry.legal_entity_id != scope.legal_entity_id:
                raise LedgerScopeMismatchError(
                    "journal entry legal_entity_id does not match ledger scope",
                )
            if entry.fiscal_year != scope.fiscal_year:
                raise LedgerScopeMismatchError(
                    "journal entry fiscal_year does not match ledger scope",
                )
            if entry.currency() != scope.currency:
                raise LedgerCurrencyMismatchError(
                    "journal entry currency does not match ledger scope currency",
                )

            for line_index, journal_line in enumerate(entry.lines):
                projected_lines.append(
                    LedgerLine(
                        journal_entry_id=entry.id,
                        posting_date=entry.posting_date,
                        posted_at=entry.posted_at,
                        journal_code=entry.journal_code,
                        reference=entry.reference,
                        account_number=journal_line.account_number,
                        side=journal_line.side,
                        amount=journal_line.amount,
                        description=journal_line.description,
                        line_index=line_index,
                    ),
                )

        ordered_lines = sorted(projected_lines, key=lambda line: line.sort_key())

        by_account: dict[str, list[LedgerLine]] = {}
        for line in ordered_lines:
            by_account.setdefault(line.account_number.value, []).append(line)

        accounts = tuple(
            LedgerAccount(
                account_number=grouped_lines[0].account_number,
                currency=scope.currency,
                lines=tuple(grouped_lines),
            )
            for _, grouped_lines in sorted(by_account.items(), key=lambda item: item[0])
        )

        return Ledger(scope=scope, accounts=accounts)
