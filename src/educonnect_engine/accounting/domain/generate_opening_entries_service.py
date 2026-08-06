"""Generate an opening entry from a year-end snapshot."""

from datetime import date

from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference

from .account_number import AccountNumber
from .journal_entry import JournalEntry
from .journal_entry_id import JournalEntryId
from .journal_line import JournalLine
from .opening_entry import OpeningEntry
from .year_end_snapshot import YearEndSnapshot


class EmptyOpeningEntryError(Exception):
    """Raised when a snapshot contains no balance to carry forward."""


class OpeningEntryRetainedEarningsAccountConflictError(Exception):
    """Raised when the retained-earnings account is already a carried account."""


class OpeningEntryTargetFiscalYearError(Exception):
    """Raised when the requested target fiscal year is not consecutive."""


class GenerateOpeningEntriesService:
    """Pure domain service generating an opening entry from frozen statements."""

    @classmethod
    def generate(
        cls,
        *,
        snapshot: YearEndSnapshot,
        journal_entry_id: JournalEntryId,
        target_fiscal_year: FiscalYear,
        journal_code: JournalCode,
        reference: JournalReference,
        posting_date: date,
        retained_earnings_account_number: AccountNumber,
    ) -> OpeningEntry:
        """Generate deterministic carried-forward lines for the next fiscal year."""
        if target_fiscal_year.value != snapshot.fiscal_year.value + 1:
            raise OpeningEntryTargetFiscalYearError(
                "target fiscal year must immediately follow snapshot fiscal year",
            )

        balance_sheet = snapshot.financial_statements.balance_sheet
        carried_lines = (
            *balance_sheet.assets.lines,
            *balance_sheet.liabilities.lines,
            *balance_sheet.equity.lines,
        )
        if any(line.account_number == retained_earnings_account_number for line in carried_lines):
            raise OpeningEntryRetainedEarningsAccountConflictError(
                "retained earnings account must not collide with a carried account",
            )

        journal_lines = [
            JournalLine(
                account_number=line.account_number,
                side=line.balance_side,
                amount=line.balance_amount,
                description="Opening balance",
            )
            for line in carried_lines
            if line.balance_side is not None and line.balance_amount.amount != 0
        ]
        result = balance_sheet.current_period_result
        if result.result_side is not None and result.result_amount.amount != 0:
            journal_lines.append(
                JournalLine(
                    account_number=retained_earnings_account_number,
                    side=result.result_side,
                    amount=result.result_amount,
                    description="Opening retained earnings",
                ),
            )
        if not journal_lines:
            raise EmptyOpeningEntryError("year-end snapshot has no opening balances")

        journal_lines.sort(key=lambda line: line.account_number.value)
        journal_entry = JournalEntry.from_recorded(
            id=journal_entry_id,
            legal_entity_id=snapshot.legal_entity_id,
            fiscal_year=target_fiscal_year,
            journal_code=journal_code,
            reference=reference,
            posting_date=posting_date,
            lines=tuple(journal_lines),
        )
        return OpeningEntry.generate(
            source_snapshot_id=snapshot.id,
            source_legal_entity_id=snapshot.legal_entity_id,
            source_fiscal_year=snapshot.fiscal_year,
            journal_entry=journal_entry,
        )
