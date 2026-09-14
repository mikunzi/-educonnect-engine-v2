import re
from decimal import Decimal

from educonnect_engine.accounting.depreciation import (
    MACHINE,
    AccountingMethod,
    DepreciationProblem,
    solve,
)
from educonnect_engine.pedagogy.domain.exercise import build_depreciation_exercise
from educonnect_engine.pedagogy.domain.generator import generate_depreciation_problem


def _problem(accounting_method: AccountingMethod) -> DepreciationProblem:
    return DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=accounting_method,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )


def test_build_from_generated_problem_keeps_original_problem_accessible():
    problem = _problem(AccountingMethod.DIRECT)

    exercise = build_depreciation_exercise(problem)

    assert exercise.problem == problem


def test_expected_answer_is_derived_from_accounting_solve():
    problem = _problem(AccountingMethod.DIRECT)
    solution = solve(problem)

    exercise = build_depreciation_exercise(problem)

    assert exercise.expected_answer.depreciation_amount == solution.depreciation_amount
    assert exercise.expected_answer.depreciation_amount == Decimal("12000")
    assert exercise.expected_answer.entry_amount == solution.entry_amount == Decimal("12000")
    assert exercise.expected_answer.carrying_amount == solution.carrying_amount == Decimal("48000")


def test_direct_method_expected_answer_and_correction():
    problem = _problem(AccountingMethod.DIRECT)

    exercise = build_depreciation_exercise(problem)

    assert exercise.expected_answer.debit_account == "6800"
    assert exercise.expected_answer.credit_account == "1500"

    method_explanation = exercise.correction.method_explanation.lower()
    assert "directe" in method_explanation
    assert "compte de l'actif" in method_explanation


def test_indirect_method_expected_answer_and_correction():
    problem = _problem(AccountingMethod.INDIRECT)

    exercise = build_depreciation_exercise(problem)

    assert exercise.expected_answer.debit_account == "6800"
    assert exercise.expected_answer.credit_account == "1509"

    method_explanation = exercise.correction.method_explanation.lower()
    assert "indirecte" in method_explanation
    assert "valeur d'acquisition" in method_explanation
    assert "ajustement de valeur" in method_explanation


def test_correction_structurally_represents_the_calculation():
    """`CalculationStep` carries raw semantic values only — no formatted text.

    Formatting (Swiss thousands separator, percentage display) is a
    presentation concern; see `tests/test_formatting.py` and
    `tests/test_web_depreciation_practice.py` for the rendered output.
    """
    problem = _problem(AccountingMethod.DIRECT)

    exercise = build_depreciation_exercise(problem)
    steps = exercise.correction.calculation_steps

    assert len(steps) >= 2

    depreciation_step = next(step for step in steps if step.result == Decimal("12000"))
    assert depreciation_step.left_operand == Decimal("60000")
    assert depreciation_step.operator == "x"
    assert depreciation_step.right_operand == Decimal("0.20")
    assert depreciation_step.right_operand_is_rate is True
    assert depreciation_step.unit == "CHF"
    assert depreciation_step.explanation

    carrying_amount_step = next(step for step in steps if step.result == Decimal("48000"))
    assert carrying_amount_step.left_operand == Decimal("60000")
    assert carrying_amount_step.operator == "-"
    assert carrying_amount_step.right_operand == Decimal("12000")
    assert carrying_amount_step.right_operand_is_rate is False
    assert carrying_amount_step.unit == "CHF"
    assert carrying_amount_step.explanation


def test_prompt_asks_for_required_outcomes_without_the_answer():
    problem = _problem(AccountingMethod.DIRECT)
    solution = solve(problem)

    exercise = build_depreciation_exercise(problem)
    prompt = exercise.prompt

    prompt_lower = prompt.lower()
    assert "amortissement" in prompt_lower
    assert "écriture" in prompt_lower
    assert "valeur comptable nette" in prompt_lower

    assert str(solution.depreciation_amount) not in prompt
    assert str(solution.carrying_amount) not in prompt
    assert solution.debit_account not in prompt
    assert solution.credit_account not in prompt


def test_swiss_terminology_is_used_and_pcg_terminology_is_avoided():
    problem = _problem(AccountingMethod.INDIRECT)

    exercise = build_depreciation_exercise(problem)

    all_text = " ".join(
        [
            exercise.prompt,
            exercise.correction.accounting_explanation,
            exercise.correction.carrying_amount_explanation_prefix,
            exercise.correction.carrying_amount_explanation_suffix,
            exercise.correction.method_explanation,
        ]
    ).lower()

    for term in ("valeur d'acquisition", "amortissement", "valeur comptable nette"):
        assert term in all_text

    assert "débit" in all_text or "débité" in all_text
    assert "crédit" in all_text or "crédité" in all_text

    # Swiss terminology, not French-PCG terminology.
    assert "dotation aux amortissements" not in all_text
    assert "valeur nette comptable" not in all_text


def test_building_the_exercise_is_deterministic():
    problem = _problem(AccountingMethod.INDIRECT)

    first = build_depreciation_exercise(problem)
    second = build_depreciation_exercise(problem)

    assert first == second


def test_generated_problems_across_seeds_can_always_be_built_into_an_exercise():
    for seed in range(10):
        problem = generate_depreciation_problem(seed=seed)
        build_depreciation_exercise(problem)  # must not raise


def test_expected_answer_matches_accounting_solve_field_by_field_for_generated_problems():
    for seed in range(10):
        problem = generate_depreciation_problem(seed=seed)
        solution = solve(problem)

        exercise = build_depreciation_exercise(problem)
        answer = exercise.expected_answer

        assert answer.depreciation_amount == solution.depreciation_amount
        assert answer.debit_account == solution.debit_account
        assert answer.credit_account == solution.credit_account
        assert answer.entry_amount == solution.entry_amount
        assert answer.carrying_amount == solution.carrying_amount


# --- Closure Part C: economic rationale ---


def test_economic_rationale_covers_the_required_points():
    problem = _problem(AccountingMethod.DIRECT)

    exercise = build_depreciation_exercise(problem)
    rationale = exercise.economic_rationale.lower()

    # 1) the asset has been used during the accounting period
    assert "utilis" in rationale
    # 2) use/time causes a loss of value
    assert "perte de valeur" in rationale
    # 3) keeping it at acquisition value would overstate the balance sheet
    assert "surévaluerait" in rationale or "sur-évaluerait" in rationale
    # 4) depreciation records that loss of value for the period
    assert "amortissement" in rationale


def test_economic_rationale_does_not_leak_the_solution():
    problem = _problem(AccountingMethod.DIRECT)
    solution = solve(problem)

    exercise = build_depreciation_exercise(problem)
    rationale = exercise.economic_rationale

    assert str(solution.depreciation_amount) not in rationale
    assert str(solution.carrying_amount) not in rationale
    assert solution.debit_account not in rationale
    assert solution.credit_account not in rationale


def test_economic_rationale_is_deterministic_and_uses_the_context():
    problem = _problem(AccountingMethod.INDIRECT)

    first = build_depreciation_exercise(problem)
    second = build_depreciation_exercise(problem)

    assert first.economic_rationale == second.economic_rationale
    assert problem.context in first.economic_rationale


# --- Pilot readiness trivial fixes: grammar and prompt deduplication ---


def test_economic_rationale_grammar_is_correct_for_a_plural_asset_name():
    problem = _problem(AccountingMethod.DIRECT)  # MACHINE -> asset name "Machines"

    exercise = build_depreciation_exercise(problem)
    rationale = exercise.economic_rationale

    assert not rationale.startswith("Machines a été")
    assert "Le bien" in rationale
    assert "Machines" in rationale


def test_prompt_does_not_repeat_data_already_shown_in_the_situation_block():
    problem = _problem(AccountingMethod.DIRECT)

    exercise = build_depreciation_exercise(problem)

    assert problem.context not in exercise.prompt
    assert str(problem.acquisition_value) not in exercise.prompt


# --- Presentation boundary cleanup: no formatted text in domain fields ---


def test_domain_correction_carries_no_swiss_formatted_text():
    """The domain must never pre-format numbers — that is presentation's job.

    French prose legitimately contains apostrophes for elision (e.g.
    "l'amortissement"), so this specifically checks for the Swiss
    thousands-separator pattern (a digit, an apostrophe, another digit)
    rather than for any apostrophe at all.
    """
    thousands_separator = re.compile(r"\d'\d")
    problem = _problem(AccountingMethod.DIRECT)

    exercise = build_depreciation_exercise(problem)
    correction = exercise.correction

    prose = [
        correction.carrying_amount_explanation_prefix,
        correction.carrying_amount_explanation_suffix,
        correction.accounting_explanation,
        correction.method_explanation,
        exercise.prompt,
        exercise.economic_rationale,
    ]
    for text in prose:
        assert thousands_separator.search(text) is None

    for step in correction.calculation_steps:
        # Raw Decimal operands — never a pre-formatted string.
        assert isinstance(step.left_operand, Decimal)
        assert isinstance(step.right_operand, Decimal)
