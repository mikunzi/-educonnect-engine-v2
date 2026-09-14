import dataclasses
from dataclasses import replace

import pytest

from educonnect_engine.accounting.depreciation import DepreciationProblem, solve
from educonnect_engine.pedagogy.application.depreciation_practice import (
    AccountingPhaseClosedError,
    ComparisonNotAttemptedError,
    ComparisonPhaseNotUnlockedError,
    DepreciationPracticeSession,
    PracticePhase,
)
from educonnect_engine.pedagogy.domain.diagnostics import (
    FeedbackComponent,
    FeedbackKind,
    LearnerAttempt,
    diagnose,
)
from educonnect_engine.pedagogy.domain.exercise import build_depreciation_exercise
from educonnect_engine.pedagogy.domain.generator import generate_depreciation_problem
from educonnect_engine.pedagogy.domain.method_comparison import (
    ComparisonAttempt,
    DepreciationMethodComparison,
    build_method_comparison,
)


def _correct_attempt_for(problem: DepreciationProblem) -> LearnerAttempt:
    solution = solve(problem)
    return LearnerAttempt(
        depreciation_amount=solution.depreciation_amount,
        debit_account=solution.debit_account,
        credit_account=solution.credit_account,
        entry_amount=solution.entry_amount,
        carrying_amount=solution.carrying_amount,
    )


def _vcn_attempt_for(problem: DepreciationProblem) -> LearnerAttempt:
    solution = solve(problem)
    return replace(_correct_attempt_for(problem), depreciation_amount=solution.carrying_amount)


def _correct_comparison_attempt_for(
    comparison: DepreciationMethodComparison,
) -> ComparisonAttempt:
    return ComparisonAttempt(
        direct_credited_account=comparison.direct.credited_account,
        indirect_credited_account=comparison.indirect.credited_account,
        direct_presented_asset_value=comparison.direct.asset_value_presented,
        indirect_acquisition_value_shown=comparison.indirect.asset_value_presented,
        indirect_adjustment_amount=comparison.indirect.adjustment_account_balance,
        direct_carrying_amount=comparison.direct.carrying_amount,
        indirect_carrying_amount=comparison.indirect.carrying_amount,
    )


def _wrong_comparison_attempt_for(
    comparison: DepreciationMethodComparison,
) -> ComparisonAttempt:
    """A deliberately incorrect (but structurally valid) comparison attempt."""
    return replace(
        _correct_comparison_attempt_for(comparison),
        indirect_adjustment_amount=comparison.indirect.adjustment_account_balance + 1,
    )


def test_start_produces_initial_practice_state_from_seed():
    problem = generate_depreciation_problem(seed=42)
    exercise = build_depreciation_exercise(problem)

    session = DepreciationPracticeSession.start(seed=42)

    assert session.problem == problem
    assert session.exercise == exercise
    assert session.attempt_number == 0
    assert session.phase == PracticePhase.ACCOUNTING
    assert session.comparison_attempted is False


def test_learner_view_does_not_expose_the_solution_before_finish():
    session = DepreciationPracticeSession.start(seed=42)

    view = session.learner_view

    assert view.problem == session.problem
    assert view.prompt == session.exercise.prompt
    assert view.economic_rationale == session.exercise.economic_rationale

    field_names = {field.name for field in dataclasses.fields(view)}
    assert field_names == {"problem", "prompt", "economic_rationale"}
    assert not hasattr(view, "expected_answer")
    assert not hasattr(view, "correction")


def test_first_submitted_attempt_uses_attempt_number_one_and_returns_diagnostic_result():
    session = DepreciationPracticeSession.start(seed=42)
    attempt = _correct_attempt_for(session.problem)

    expected_result = diagnose(session.problem, attempt, attempt_number=1)
    result = session.submit(attempt)

    assert result == expected_result
    assert session.attempt_number == 1


def test_second_attempt_uses_attempt_number_two_and_feedback_evolves_to_explanation():
    session = DepreciationPracticeSession.start(seed=42)
    problem_before = session.problem
    exercise_before = session.exercise
    wrong_attempt = _vcn_attempt_for(session.problem)

    first_result = session.submit(wrong_attempt)
    assert session.attempt_number == 1

    second_result = session.submit(wrong_attempt)
    assert session.attempt_number == 2

    # The session never regenerates the exercise/problem between attempts.
    assert session.problem == problem_before
    assert session.exercise == exercise_before

    first_depreciation_feedback = next(
        item
        for item in first_result.feedback
        if item.component == FeedbackComponent.DEPRECIATION_AMOUNT
    )
    second_depreciation_feedback = next(
        item
        for item in second_result.feedback
        if item.component == FeedbackComponent.DEPRECIATION_AMOUNT
    )

    # The application layer never decides HINT vs EXPLANATION itself — it
    # only supplies the attempt number, and diagnose()'s own rule (from the
    # AMO-001 attempt-aware feedback slice) does the rest.
    assert first_depreciation_feedback.kind == FeedbackKind.HINT
    assert second_depreciation_feedback.kind == FeedbackKind.EXPLANATION


def test_score_returned_by_submit_equals_diagnose_score():
    session = DepreciationPracticeSession.start(seed=7)
    attempt = _correct_attempt_for(session.problem)

    expected_score = diagnose(session.problem, attempt, attempt_number=1).score
    result = session.submit(attempt)

    assert result.score == expected_score


def test_attempt_number_sequences_from_zero_as_the_session_owns_it():
    session = DepreciationPracticeSession.start(seed=42)
    attempt = _correct_attempt_for(session.problem)

    assert session.attempt_number == 0
    session.submit(attempt)
    assert session.attempt_number == 1
    session.submit(attempt)
    assert session.attempt_number == 2


def test_submit_does_not_accept_a_manual_attempt_number():
    session = DepreciationPracticeSession.start(seed=42)
    attempt = _correct_attempt_for(session.problem)

    with pytest.raises(TypeError):
        session.submit(attempt, attempt_number=5)  # type: ignore[call-arg]


def test_starting_two_practices_with_the_same_seed_creates_equivalent_initial_exercises():
    first = DepreciationPracticeSession.start(seed=123)
    second = DepreciationPracticeSession.start(seed=123)

    assert first.problem == second.problem
    assert first.exercise == second.exercise
    assert first.learner_view == second.learner_view


# --- Final closure Part 1: phase lifecycle ---


def test_comparison_is_not_available_before_accounting_phase_is_completed():
    session = DepreciationPracticeSession.start(seed=42)
    session.submit(_correct_attempt_for(session.problem))

    with pytest.raises(ComparisonPhaseNotUnlockedError):
        _ = session.comparison


def test_completing_accounting_phase_unlocks_comparison():
    session = DepreciationPracticeSession.start(seed=42)
    session.submit(_correct_attempt_for(session.problem))

    session.complete_accounting_phase()

    assert session.phase == PracticePhase.COMPARISON
    expected = build_method_comparison(session.problem)
    assert session.comparison == expected


def test_completing_accounting_phase_does_not_expose_the_solution():
    session = DepreciationPracticeSession.start(seed=42)

    result = session.complete_accounting_phase()

    assert result is None
    assert session.phase == PracticePhase.COMPARISON
    # No accessor exists on the session's public surface that hands back the
    # solution at this point — only `finish()` (later, gated) does.
    assert not hasattr(session, "expected_answer")
    assert not hasattr(session, "correction")


def test_submit_comparison_rejected_before_accounting_phase_completed():
    session = DepreciationPracticeSession.start(seed=42)
    comparison = build_method_comparison(session.problem)
    attempt = _correct_comparison_attempt_for(comparison)

    with pytest.raises(ComparisonPhaseNotUnlockedError):
        session.submit_comparison(attempt)


def test_submit_comparison_allowed_once_accounting_phase_is_completed():
    session = DepreciationPracticeSession.start(seed=42)
    session.complete_accounting_phase()

    result = session.submit_comparison(_correct_comparison_attempt_for(session.comparison))

    assert result.is_fully_correct
    assert session.comparison_attempted is True


def test_finish_rejected_before_a_comparison_attempt():
    session = DepreciationPracticeSession.start(seed=42)
    session.complete_accounting_phase()

    with pytest.raises(ComparisonNotAttemptedError):
        session.finish()


def test_finish_after_comparison_attempt_exposes_model_answer_and_correction():
    session = DepreciationPracticeSession.start(seed=42)
    exercise = session.exercise
    session.complete_accounting_phase()
    session.submit_comparison(_correct_comparison_attempt_for(session.comparison))

    completed = session.finish()

    assert session.phase == PracticePhase.COMPLETED
    assert completed.problem == session.problem
    assert completed.expected_answer == exercise.expected_answer
    assert completed.correction == exercise.correction


def test_finish_allowed_even_with_an_incorrect_comparison_attempt():
    """Completion and mastery are different concerns for V1."""
    session = DepreciationPracticeSession.start(seed=42)
    session.complete_accounting_phase()
    result = session.submit_comparison(_wrong_comparison_attempt_for(session.comparison))

    assert not result.is_fully_correct

    completed = session.finish()  # must not raise

    assert completed.expected_answer == session.exercise.expected_answer


def test_finish_expected_answer_matches_accounting_solve_field_by_field():
    for seed in range(10):
        session = DepreciationPracticeSession.start(seed=seed)
        solution = solve(session.problem)

        session.complete_accounting_phase()
        session.submit_comparison(_correct_comparison_attempt_for(session.comparison))
        completed = session.finish()

        assert completed.expected_answer.depreciation_amount == solution.depreciation_amount
        assert completed.expected_answer.debit_account == solution.debit_account
        assert completed.expected_answer.credit_account == solution.credit_account
        assert completed.expected_answer.entry_amount == solution.entry_amount
        assert completed.expected_answer.carrying_amount == solution.carrying_amount


def test_submit_rejected_after_accounting_phase_closed():
    session = DepreciationPracticeSession.start(seed=42)
    attempt = _correct_attempt_for(session.problem)
    session.complete_accounting_phase()

    with pytest.raises(AccountingPhaseClosedError):
        session.submit(attempt)


def test_complete_accounting_phase_is_rejected_when_already_closed():
    session = DepreciationPracticeSession.start(seed=42)
    session.complete_accounting_phase()

    with pytest.raises(AccountingPhaseClosedError):
        session.complete_accounting_phase()


def test_full_lifecycle_from_start_to_finish_in_order():
    session = DepreciationPracticeSession.start(seed=42)

    # ACCOUNTING
    assert session.phase == PracticePhase.ACCOUNTING
    session.submit(_correct_attempt_for(session.problem))

    # -> COMPARISON
    session.complete_accounting_phase()
    assert session.phase == PracticePhase.COMPARISON
    with pytest.raises(AccountingPhaseClosedError):
        session.submit(_correct_attempt_for(session.problem))

    comparison_result = session.submit_comparison(
        _correct_comparison_attempt_for(session.comparison)
    )
    assert comparison_result.is_fully_correct

    # -> COMPLETED
    completed = session.finish()
    assert session.phase == PracticePhase.COMPLETED
    assert completed.expected_answer == session.exercise.expected_answer
    assert completed.correction == session.exercise.correction


def test_full_workflow_across_seeds_does_not_raise():
    for seed in range(10):
        session = DepreciationPracticeSession.start(seed=seed)
        attempt = _correct_attempt_for(session.problem)

        session.submit(attempt)
        session.submit(attempt)
        session.complete_accounting_phase()
        session.submit_comparison(_correct_comparison_attempt_for(session.comparison))
        session.finish()
