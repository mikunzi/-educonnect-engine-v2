"""Unit tests for FiscalYearClosingStatus enum."""

from educonnect_engine.accounting.domain.fiscal_year_closing_status import FiscalYearClosingStatus


def test_fiscal_year_closing_status_values_are_stable() -> None:
    assert FiscalYearClosingStatus.OPEN.value == "open"
    assert FiscalYearClosingStatus.CLOSED.value == "closed"
