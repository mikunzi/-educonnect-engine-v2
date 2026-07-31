"""Tests for accounting account foundations."""

import pytest

from educonnect_engine.accounting import (
    Account,
    AccountCategory,
    FinancialStatement,
    NormalBalance,
)


def test_account_creation_success() -> None:
    account = Account(
        number=1000,
        name="Cash",
        category=AccountCategory.ASSET,
        class_number=1,
        group_number=10,
        normal_balance=NormalBalance.DEBIT,
        statement=FinancialStatement.BALANCE_SHEET,
        description="Cash account",
        purpose="Track liquid assets",
        reconcilable=True,
        cash_account=True,
    )

    assert account.number == 1000
    assert account.name == "Cash"
    assert account.category is AccountCategory.ASSET
    assert account.class_number == 1
    assert account.group_number == 10
    assert account.normal_balance is NormalBalance.DEBIT
    assert account.statement is FinancialStatement.BALANCE_SHEET
    assert account.description == "Cash account"
    assert account.purpose == "Track liquid assets"
    assert account.reconcilable is True
    assert account.cash_account is True


@pytest.mark.parametrize("number", [0, -1])
def test_account_rejects_non_positive_number(number: int) -> None:
    with pytest.raises(ValueError, match="number must be positive"):
        Account(
            number=number,
            name="Cash",
            category=AccountCategory.ASSET,
            class_number=1,
            group_number=10,
            normal_balance=NormalBalance.DEBIT,
            statement=FinancialStatement.BALANCE_SHEET,
        )


@pytest.mark.parametrize("name", ["", "   "])
def test_account_rejects_empty_name(name: str) -> None:
    with pytest.raises(ValueError, match="name must not be empty"):
        Account(
            number=1000,
            name=name,
            category=AccountCategory.ASSET,
            class_number=1,
            group_number=10,
            normal_balance=NormalBalance.DEBIT,
            statement=FinancialStatement.BALANCE_SHEET,
        )


@pytest.mark.parametrize("class_number", [0, -2])
def test_account_rejects_non_positive_class_number(class_number: int) -> None:
    with pytest.raises(ValueError, match="class_number must be positive"):
        Account(
            number=1000,
            name="Cash",
            category=AccountCategory.ASSET,
            class_number=class_number,
            group_number=10,
            normal_balance=NormalBalance.DEBIT,
            statement=FinancialStatement.BALANCE_SHEET,
        )


@pytest.mark.parametrize("group_number", [0, -3])
def test_account_rejects_non_positive_group_number(group_number: int) -> None:
    with pytest.raises(ValueError, match="group_number must be positive"):
        Account(
            number=1000,
            name="Cash",
            category=AccountCategory.ASSET,
            class_number=1,
            group_number=group_number,
            normal_balance=NormalBalance.DEBIT,
            statement=FinancialStatement.BALANCE_SHEET,
        )
