from decimal import Decimal

import pytest

from educonnect_engine.accounting.depreciation import (
    FURNITURE,
    IT_EQUIPMENT,
    MACHINE,
    VEHICLE,
    AccountingMethod,
    DepreciableAsset,
    DepreciationProblem,
    solve,
)


def test_linear_depreciation_amount_is_calculated():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )

    solution = solve(problem)

    assert solution.depreciation_amount == Decimal("12000")


def test_carrying_amount_is_calculated():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )

    solution = solve(problem)

    assert solution.carrying_amount == Decimal("48000")


def test_direct_method_credits_asset_account():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )

    solution = solve(problem)

    assert solution.credit_account == "1500"


def test_indirect_method_credits_correction_account():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )

    solution = solve(problem)

    assert solution.credit_account == "1509"


def test_direct_method_produces_full_solution():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )

    solution = solve(problem)

    assert solution.depreciation_amount == Decimal("12000")
    assert solution.debit_account == "6800"
    assert solution.credit_account == "1500"
    assert solution.entry_amount == Decimal("12000")
    assert solution.carrying_amount == Decimal("48000")


def test_indirect_method_produces_full_solution():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1509"
    assert solution.entry_amount == Decimal("12000")
    assert solution.carrying_amount == Decimal("48000")


def test_acquisition_value_zero_or_negative_is_rejected():
    for invalid_value in (Decimal("0"), Decimal("-1")):
        with pytest.raises(ValueError):
            DepreciationProblem(
                acquisition_value=invalid_value,
                rate=Decimal("0.20"),
                accounting_method=AccountingMethod.DIRECT,
                asset=MACHINE,
                exercise_year=2026,
                context="Alpina Menuiserie Sàrl",
            )


def test_rate_zero_or_negative_is_rejected():
    for invalid_rate in (Decimal("0"), Decimal("-0.1")):
        with pytest.raises(ValueError):
            DepreciationProblem(
                acquisition_value=Decimal("60000"),
                rate=invalid_rate,
                accounting_method=AccountingMethod.DIRECT,
                asset=MACHINE,
                exercise_year=2026,
                context="Alpina Menuiserie Sàrl",
            )


def test_rate_of_one_hundred_percent_or_more_is_rejected():
    for invalid_rate in (Decimal("1"), Decimal("1.5")):
        with pytest.raises(ValueError):
            DepreciationProblem(
                acquisition_value=Decimal("60000"),
                rate=invalid_rate,
                accounting_method=AccountingMethod.DIRECT,
                asset=MACHINE,
                exercise_year=2026,
                context="Alpina Menuiserie Sàrl",
            )


def test_indirect_method_without_correction_account_is_rejected():
    asset_without_correction_account = DepreciableAsset(
        name="Mobilier",
        asset_account="1510",
        expense_account="6801",
        correction_account=None,
    )

    with pytest.raises(ValueError):
        DepreciationProblem(
            acquisition_value=Decimal("60000"),
            rate=Decimal("0.20"),
            accounting_method=AccountingMethod.INDIRECT,
            asset=asset_without_correction_account,
            exercise_year=2026,
            context="Alpina Menuiserie Sàrl",
        )


# --- Closure Part A: explicit non-MACHINE account-mapping regression tests ---


def test_furniture_direct_credits_1510():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=FURNITURE,
        exercise_year=2026,
        context="Restaurant Le Trèfle Sàrl",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1510"


def test_furniture_indirect_credits_1519():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=FURNITURE,
        exercise_year=2026,
        context="Restaurant Le Trèfle Sàrl",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1519"


def test_it_equipment_direct_credits_1520():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=IT_EQUIPMENT,
        exercise_year=2026,
        context="Cabinet fiduciaire Fiduco Sàrl",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1520"


def test_it_equipment_indirect_credits_1529():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=IT_EQUIPMENT,
        exercise_year=2026,
        context="Cabinet fiduciaire Fiduco Sàrl",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1529"


def test_vehicle_direct_credits_1530():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=VEHICLE,
        exercise_year=2026,
        context="Entreprise de transport Transalpine SA",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1530"


def test_vehicle_indirect_credits_1539():
    problem = DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.INDIRECT,
        asset=VEHICLE,
        exercise_year=2026,
        context="Entreprise de transport Transalpine SA",
    )

    solution = solve(problem)

    assert solution.debit_account == "6800"
    assert solution.credit_account == "1539"


def test_all_supported_assets_use_expense_account_6800():
    for asset in (MACHINE, FURNITURE, IT_EQUIPMENT, VEHICLE):
        assert asset.expense_account == "6800"
