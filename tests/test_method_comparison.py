from dataclasses import replace
from decimal import Decimal

from educonnect_engine.accounting.depreciation import (
    MACHINE,
    AccountingMethod,
    DepreciationProblem,
    solve,
)
from educonnect_engine.pedagogy.domain.generator import generate_depreciation_problem
from educonnect_engine.pedagogy.domain.method_comparison import (
    ComparisonAttempt,
    ComparisonComponent,
    DepreciationMethodComparison,
    build_method_comparison,
    verify_comparison_attempt,
)


def _machine_problem() -> DepreciationProblem:
    return DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )


def _correct_comparison_attempt(comparison: DepreciationMethodComparison) -> ComparisonAttempt:
    return ComparisonAttempt(
        direct_credited_account=comparison.direct.credited_account,
        indirect_credited_account=comparison.indirect.credited_account,
        direct_presented_asset_value=comparison.direct.asset_value_presented,
        indirect_acquisition_value_shown=comparison.indirect.asset_value_presented,
        indirect_adjustment_amount=comparison.indirect.adjustment_account_balance,
        direct_carrying_amount=comparison.direct.carrying_amount,
        indirect_carrying_amount=comparison.indirect.carrying_amount,
    )


# --- Part D: DepreciationMethodComparison ---


def test_direct_presentation_matches_specification():
    problem = _machine_problem()

    comparison = build_method_comparison(problem)

    assert comparison.direct.credited_account == "1500"
    assert comparison.direct.asset_value_presented == Decimal("48000")
    assert comparison.direct.adjustment_account_balance == Decimal("0")
    assert comparison.direct.carrying_amount == Decimal("48000")


def test_indirect_presentation_matches_specification():
    problem = _machine_problem()

    comparison = build_method_comparison(problem)

    assert comparison.indirect.credited_account == "1509"
    assert comparison.indirect.asset_value_presented == Decimal("60000")
    assert comparison.indirect.adjustment_account_balance == Decimal("12000")
    assert comparison.indirect.carrying_amount == Decimal("48000")


def test_both_methods_agree_on_the_same_carrying_amount():
    problem = _machine_problem()

    comparison = build_method_comparison(problem)

    assert comparison.direct.carrying_amount == comparison.indirect.carrying_amount


def test_indirect_keeps_acquisition_value_separate_from_adjustment_amount():
    problem = _machine_problem()

    comparison = build_method_comparison(problem)

    assert comparison.indirect.asset_value_presented == problem.acquisition_value
    assert (
        comparison.indirect.asset_value_presented
        != comparison.indirect.adjustment_account_balance
    )


def test_comparison_is_built_from_accounting_solve_for_generated_problems():
    for seed in range(10):
        problem = generate_depreciation_problem(seed=seed)
        comparison = build_method_comparison(problem)

        direct_solution = solve(replace(problem, accounting_method=AccountingMethod.DIRECT))
        indirect_solution = solve(replace(problem, accounting_method=AccountingMethod.INDIRECT))

        assert comparison.direct.credited_account == direct_solution.credit_account
        assert comparison.direct.carrying_amount == direct_solution.carrying_amount
        assert comparison.indirect.credited_account == indirect_solution.credit_account
        assert comparison.indirect.carrying_amount == indirect_solution.carrying_amount
        assert (
            comparison.indirect.adjustment_account_balance == indirect_solution.depreciation_amount
        )


# --- Part E: learner comparison attempt + verification ---


def test_fully_correct_comparison_attempt_is_fully_correct():
    problem = _machine_problem()
    comparison = build_method_comparison(problem)
    attempt = _correct_comparison_attempt(comparison)

    result = verify_comparison_attempt(comparison, attempt)

    assert result.incorrect_components == frozenset()
    assert result.is_fully_correct


def test_confused_direct_and_indirect_accounts_are_detected():
    problem = _machine_problem()
    comparison = build_method_comparison(problem)
    attempt = replace(
        _correct_comparison_attempt(comparison),
        direct_credited_account=comparison.indirect.credited_account,
        indirect_credited_account=comparison.direct.credited_account,
    )

    result = verify_comparison_attempt(comparison, attempt)

    assert ComparisonComponent.DIRECT_CREDITED_ACCOUNT in result.incorrect_components
    assert ComparisonComponent.INDIRECT_CREDITED_ACCOUNT in result.incorrect_components
    assert not result.is_fully_correct


def test_mismatched_carrying_amounts_between_methods_are_detected():
    problem = _machine_problem()
    comparison = build_method_comparison(problem)
    attempt = replace(
        _correct_comparison_attempt(comparison),
        indirect_carrying_amount=Decimal("50000"),
    )

    result = verify_comparison_attempt(comparison, attempt)

    assert ComparisonComponent.INDIRECT_CARRYING_AMOUNT in result.incorrect_components
    assert ComparisonComponent.DIRECT_CARRYING_AMOUNT in result.correct_components


def test_netting_acquisition_value_with_adjustment_is_detected_as_incorrect():
    problem = _machine_problem()
    comparison = build_method_comparison(problem)
    # A common learner mistake: showing the *net* value instead of keeping
    # acquisition value and the adjustment separate.
    attempt = replace(
        _correct_comparison_attempt(comparison),
        indirect_acquisition_value_shown=comparison.indirect.carrying_amount,
    )

    result = verify_comparison_attempt(comparison, attempt)

    assert ComparisonComponent.INDIRECT_ACQUISITION_VALUE_SHOWN in result.incorrect_components


def test_inconsistent_table_values_are_flagged_component_by_component():
    problem = _machine_problem()
    comparison = build_method_comparison(problem)
    attempt = replace(
        _correct_comparison_attempt(comparison),
        direct_presented_asset_value=Decimal("999"),
    )

    result = verify_comparison_attempt(comparison, attempt)

    assert ComparisonComponent.DIRECT_PRESENTED_ASSET_VALUE in result.incorrect_components
    # Everything else about this attempt is still correct.
    assert len(result.incorrect_components) == 1
