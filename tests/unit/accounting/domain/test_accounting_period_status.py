"""Unit tests for AccountingPeriodStatus enum."""

from educonnect_engine.accounting.domain.accounting_period_status import AccountingPeriodStatus


def test_accounting_period_status_values_are_stable() -> None:
    assert AccountingPeriodStatus.OPEN.value == "open"
    assert AccountingPeriodStatus.CLOSED.value == "closed"
    assert AccountingPeriodStatus.LOCKED.value == "locked"
