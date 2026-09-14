import random
from decimal import Decimal

from educonnect_engine.accounting.depreciation import (
    AccountingMethod,
    DepreciationProblem,
    solve,
)
from educonnect_engine.pedagogy.domain.generator import (
    ACQUISITION_VALUES,
    RATES,
    SCENARIO_TEMPLATES,
    generate_depreciation_problem,
)

_SEEDS = range(20)


def test_generate_returns_a_valid_depreciation_problem():
    problem = generate_depreciation_problem(seed=1)

    assert isinstance(problem, DepreciationProblem)


def test_generated_acquisition_value_is_always_from_the_allowed_pool():
    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        assert problem.acquisition_value in ACQUISITION_VALUES


def test_generated_rate_is_always_from_the_allowed_pool():
    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        assert problem.rate in RATES


def test_generated_asset_is_always_from_the_supported_catalogue():
    supported_assets = {template.asset for template in SCENARIO_TEMPLATES}

    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        assert problem.asset in supported_assets


def test_generated_accounting_method_is_direct_or_indirect():
    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        assert problem.accounting_method in (AccountingMethod.DIRECT, AccountingMethod.INDIRECT)


def test_same_seed_produces_the_same_problem():
    assert generate_depreciation_problem(seed=42) == generate_depreciation_problem(seed=42)


def test_different_seeds_can_produce_different_problems():
    problems = {generate_depreciation_problem(seed=seed) for seed in _SEEDS}

    assert len(problems) > 1


def test_every_generated_problem_can_be_solved_without_raising():
    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        solve(problem)


def test_carrying_amount_equals_acquisition_value_minus_depreciation_amount():
    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        solution = solve(problem)

        assert solution.carrying_amount == problem.acquisition_value - solution.depreciation_amount


def test_context_and_asset_always_come_from_a_known_scenario_template():
    known_pairs = {(template.context, template.asset) for template in SCENARIO_TEMPLATES}

    for seed in _SEEDS:
        problem = generate_depreciation_problem(seed=seed)
        assert (problem.context, problem.asset) in known_pairs


def test_generation_does_not_mutate_global_random_state():
    random.seed(1234)
    expected_next_value = random.random()

    random.seed(1234)
    generate_depreciation_problem(seed=999)
    actual_next_value = random.random()

    assert actual_next_value == expected_next_value


def test_allowed_pools_match_the_specification():
    assert set(ACQUISITION_VALUES) == {
        Decimal("24000"),
        Decimal("30000"),
        Decimal("36000"),
        Decimal("48000"),
        Decimal("60000"),
        Decimal("75000"),
        Decimal("80000"),
        Decimal("100000"),
    }
    assert set(RATES) == {
        Decimal("0.10"),
        Decimal("0.125"),
        Decimal("0.20"),
        Decimal("0.25"),
    }
