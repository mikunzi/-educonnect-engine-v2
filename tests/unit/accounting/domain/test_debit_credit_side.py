"""Unit tests for DebitCreditSide enum."""

from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide


def test_debit_credit_side_values() -> None:
    assert DebitCreditSide.DEBIT.value == "debit"
    assert DebitCreditSide.CREDIT.value == "credit"
