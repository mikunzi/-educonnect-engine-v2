"""End-to-end accounting cycle integration test.

This test validates the full in-memory accounting cycle using existing
use cases and domain services only.
"""

import runpy
from decimal import Decimal
from pathlib import Path

from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide


def test_accounting_full_cycle_end_to_end() -> None:
    """Validate the complete accounting flow from recording to opening entries."""
    module_path = Path(__file__).resolve().parents[3] / "examples" / "accounting_full_cycle.py"
    namespace = runpy.run_path(str(module_path))
    run_accounting_full_cycle = namespace["run_accounting_full_cycle"]

    result = run_accounting_full_cycle()

    # 1. All journal entries are balanced.
    for entry in result.posted_entries:
        assert entry.total_debit().amount == entry.total_credit().amount

    # 2. Ledger contains all posted fiscal-year movements.
    assert len(result.posted_entries) == 5
    assert len(result.ledger.accounts) == 6

    # 3. Trial Balance is balanced.
    assert result.trial_balance.total_debit().amount == Decimal("195000.00")
    assert result.trial_balance.total_credit().amount == Decimal("195000.00")
    assert result.trial_balance.is_balanced() is True

    # 4. Balance Sheet equation remains valid.
    assert result.balance_sheet.assets_total().amount == Decimal("130000.00")
    assert result.balance_sheet.right_side_total().amount == Decimal("130000.00")
    assert result.balance_sheet.is_balanced() is True

    # 5. Income Statement equals revenues - expenses.
    assert result.income_statement.revenue_total().amount == Decimal("35000.00")
    assert result.income_statement.expense_total().amount == Decimal("5000.00")
    assert result.income_statement.net_result_amount().amount == Decimal("30000.00")
    assert result.income_statement.net_result_side() is DebitCreditSide.CREDIT

    # 6. Financial statements are coherent.
    assert (
        result.financial_statements.income_statement.net_result_amount().amount
        == result.financial_statements.balance_sheet.current_period_result.result_amount.amount
    )

    # 7. Snapshot matches the fiscal year.
    assert result.snapshot.fiscal_year.value == 2026

    # 8. Fiscal year closing is valid.
    assert result.closing_result.version == 1

    # 9. Opening entry contains only balance-sheet accounts and retained earnings.
    opening_accounts = {
        line.account_number.value for line in result.opening_entry.journal_entry.lines
    }
    assert "3400" not in opening_accounts
    assert "6000" not in opening_accounts
    assert opening_accounts == {"1020", "1500", "2800", "2990"}

    # 10. Opening entry is balanced.
    opening = result.opening_entry.journal_entry
    assert opening.total_debit().amount == Decimal("130000.00")
    assert opening.total_credit().amount == Decimal("130000.00")
