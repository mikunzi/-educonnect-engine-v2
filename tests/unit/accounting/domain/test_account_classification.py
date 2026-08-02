"""Unit tests for AccountClassification enum."""

from educonnect_engine.accounting.domain.account_classification import AccountClassification


def test_account_classification_values_are_stable() -> None:
    assert AccountClassification.ASSET.value == "asset"
    assert AccountClassification.LIABILITY.value == "liability"
    assert AccountClassification.EQUITY.value == "equity"
    assert AccountClassification.REVENUE.value == "revenue"
    assert AccountClassification.EXPENSE.value == "expense"
