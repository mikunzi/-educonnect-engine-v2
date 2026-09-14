from dataclasses import replace
from decimal import Decimal

import pytest

from educonnect_engine.accounting.depreciation import (
    MACHINE,
    AccountingMethod,
    DepreciationProblem,
)
from educonnect_engine.pedagogy.domain.diagnostics import (
    DiagnosticErrorCode,
    FeedbackComponent,
    FeedbackKind,
    LearnerAttempt,
    diagnose,
)


def _direct_problem() -> DepreciationProblem:
    return DepreciationProblem(
        acquisition_value=Decimal("60000"),
        rate=Decimal("0.20"),
        accounting_method=AccountingMethod.DIRECT,
        asset=MACHINE,
        exercise_year=2026,
        context="Alpina Menuiserie Sàrl",
    )


def _correct_attempt() -> LearnerAttempt:
    return LearnerAttempt(
        depreciation_amount=Decimal("12000"),
        debit_account="6800",
        credit_account="1500",
        entry_amount=Decimal("12000"),
        carrying_amount=Decimal("48000"),
    )


def test_vcn_instead_of_depreciation_is_detected():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("48000"))

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION in result.error_codes


def test_arbitrary_wrong_amount_is_not_classified_as_vcn():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("9999"))

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION not in result.error_codes


def test_reversed_entry_is_detected():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), debit_account="1500", credit_account="6800")

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.REVERSED_ENTRY in result.error_codes


def test_correct_attempt_has_no_diagnostics():
    problem = _direct_problem()
    attempt = _correct_attempt()

    result = diagnose(problem, attempt, attempt_number=1)

    assert result.error_codes == frozenset()


def test_fully_correct_attempt_scores_maximum():
    problem = _direct_problem()
    attempt = _correct_attempt()

    result = diagnose(problem, attempt, attempt_number=1)

    assert result.score == 10
    assert result.max_score == 10


def test_correct_amounts_but_wrong_accounts_award_only_correct_components():
    problem = _direct_problem()
    attempt = replace(
        _correct_attempt(),
        debit_account="6900",
        credit_account="2000",
        entry_amount=Decimal("9999"),
    )

    result = diagnose(problem, attempt, attempt_number=1)

    assert result.score == 5  # depreciation_amount (4) + carrying_amount (1)
    assert result.max_score == 10


def test_correct_accounts_but_wrong_depreciation_amount_keeps_account_points():
    problem = _direct_problem()
    attempt = replace(
        _correct_attempt(),
        depreciation_amount=Decimal("15000"),
        entry_amount=Decimal("15000"),
        carrying_amount=Decimal("45000"),
    )

    result = diagnose(problem, attempt, attempt_number=1)

    assert result.score == 4  # debit_account (2) + credit_account (2)
    assert result.max_score == 10


def test_reversed_entry_scores_components_instead_of_zero():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), debit_account="1500", credit_account="6800")

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.REVERSED_ENTRY in result.error_codes
    assert result.score == 6  # depreciation_amount (4) + entry_amount (1) + carrying_amount (1)


def test_vcn_still_detected_while_carrying_amount_scores_independently():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("48000"))

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION in result.error_codes
    # debit_account (2) + credit_account (2) + entry_amount (1) + carrying_amount (1)
    assert result.score == 6


def test_fully_correct_attempt_feedback_is_a_single_confirmation():
    problem = _direct_problem()
    attempt = _correct_attempt()

    result = diagnose(problem, attempt, attempt_number=1)

    assert result.score == 10
    assert result.error_codes == frozenset()
    assert len(result.feedback) == 1

    confirmation = result.feedback[0]
    assert confirmation.kind == FeedbackKind.CORRECT
    assert confirmation.message


def test_fully_correct_attempt_feedback_is_correct_regardless_of_attempt_number():
    problem = _direct_problem()
    attempt = _correct_attempt()

    for attempt_number in (1, 2, 5):
        result = diagnose(problem, attempt, attempt_number=attempt_number)

        assert len(result.feedback) == 1
        assert result.feedback[0].kind == FeedbackKind.CORRECT


def test_vcn_feedback_on_first_attempt_is_a_targeted_hint_not_an_explanation():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("48000"))

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION in result.error_codes

    depreciation_feedback = [
        item for item in result.feedback if item.component == FeedbackComponent.DEPRECIATION_AMOUNT
    ]
    assert len(depreciation_feedback) == 1
    item = depreciation_feedback[0]

    assert item.kind == FeedbackKind.HINT
    assert item.code == DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION

    message = item.message.lower()
    # A targeted hint may name the two concepts to help the learner tell them
    # apart, but it must not do the full mapping ("your 48000 is the VCN").
    assert "valeur comptable nette" in message
    assert "48000" not in item.message


def test_vcn_feedback_on_second_attempt_explains_carrying_amount_confusion():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("48000"))

    result = diagnose(problem, attempt, attempt_number=2)

    assert result.error_codes == frozenset({DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION})

    depreciation_feedback = [
        item for item in result.feedback if item.component == FeedbackComponent.DEPRECIATION_AMOUNT
    ]
    assert len(depreciation_feedback) == 1
    item = depreciation_feedback[0]

    assert item.kind == FeedbackKind.EXPLANATION
    assert item.code == DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION
    assert "48000" in item.message
    assert "valeur comptable nette" in item.message.lower()

    codes_in_feedback = {feedback_item.code for feedback_item in result.feedback}
    assert codes_in_feedback <= {None, DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION}


def test_reversed_entry_feedback_on_first_attempt_is_a_hint_not_the_full_entry():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), debit_account="1500", credit_account="6800")

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.REVERSED_ENTRY in result.error_codes

    journal_feedback = [
        item for item in result.feedback if item.component == FeedbackComponent.JOURNAL_ENTRY
    ]
    assert len(journal_feedback) == 1
    item = journal_feedback[0]

    assert item.kind == FeedbackKind.HINT
    assert item.code == DiagnosticErrorCode.REVERSED_ENTRY

    message = item.message.lower()
    # Must not directly hand over the correct journal entry yet.
    assert "doit être débitée" not in message
    assert "doit être crédité" not in message


def test_reversed_entry_feedback_on_second_attempt_explains_accounting_direction():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), debit_account="1500", credit_account="6800")

    result = diagnose(problem, attempt, attempt_number=2)

    assert DiagnosticErrorCode.REVERSED_ENTRY in result.error_codes

    journal_feedback = [
        item for item in result.feedback if item.component == FeedbackComponent.JOURNAL_ENTRY
    ]
    assert len(journal_feedback) == 1
    item = journal_feedback[0]

    assert item.kind == FeedbackKind.EXPLANATION
    assert item.code == DiagnosticErrorCode.REVERSED_ENTRY

    message = item.message.lower()
    assert "débit" in message
    assert "crédit" in message


def test_arbitrary_wrong_amount_feedback_invites_recalculation_without_diagnosis():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("47500"))

    result = diagnose(problem, attempt, attempt_number=1)

    assert DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION not in result.error_codes

    depreciation_feedback = [
        item for item in result.feedback if item.component == FeedbackComponent.DEPRECIATION_AMOUNT
    ]
    assert len(depreciation_feedback) == 1
    item = depreciation_feedback[0]
    assert item.kind == FeedbackKind.HINT
    assert item.code is None

    message = item.message.lower()
    assert "valeur comptable nette" not in message
    assert "recalcul" in message


def test_arbitrary_wrong_amount_feedback_stays_a_generic_hint_on_later_attempts():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("47500"))

    for attempt_number in (1, 2, 5):
        result = diagnose(problem, attempt, attempt_number=attempt_number)

        assert result.error_codes == frozenset()

        depreciation_feedback = [
            item
            for item in result.feedback
            if item.component == FeedbackComponent.DEPRECIATION_AMOUNT
        ]
        assert len(depreciation_feedback) == 1
        item = depreciation_feedback[0]

        # Increasing attempt_number must never fabricate an EXPLANATION for
        # an amount that no deterministic error code explains.
        assert item.kind == FeedbackKind.HINT
        assert item.code is None


def test_partial_attempt_acknowledges_correct_components_and_targets_credit_account():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), credit_account="2000")

    result = diagnose(problem, attempt, attempt_number=1)

    assert result.error_codes == frozenset()
    assert any(item.kind == FeedbackKind.CORRECT for item in result.feedback)

    credit_feedback = [
        item for item in result.feedback if item.component == FeedbackComponent.CREDIT_ACCOUNT
    ]
    assert len(credit_feedback) == 1
    assert credit_feedback[0].kind == FeedbackKind.HINT

    assert not any(item.component == FeedbackComponent.DEBIT_ACCOUNT for item in result.feedback)
    assert not any(
        item.component == FeedbackComponent.OVERALL and item.kind != FeedbackKind.CORRECT
        for item in result.feedback
    )


def test_diagnosis_and_score_are_independent_of_attempt_number():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), depreciation_amount=Decimal("48000"))

    first_attempt_result = diagnose(problem, attempt, attempt_number=1)
    later_attempt_result = diagnose(problem, attempt, attempt_number=5)

    assert first_attempt_result.error_codes == later_attempt_result.error_codes
    assert first_attempt_result.score == later_attempt_result.score
    assert first_attempt_result.max_score == later_attempt_result.max_score


def test_attempt_number_zero_or_negative_is_rejected():
    problem = _direct_problem()
    attempt = _correct_attempt()

    for invalid_attempt_number in (0, -1):
        with pytest.raises(ValueError):
            diagnose(problem, attempt, attempt_number=invalid_attempt_number)


# --- Closure Part B: generic (non-diagnosed) HINT stays HINT on later attempts ---


def test_wrong_debit_account_without_reversal_stays_hint_across_attempts():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), debit_account="6900")

    for attempt_number in (1, 2, 5):
        result = diagnose(problem, attempt, attempt_number=attempt_number)

        assert DiagnosticErrorCode.REVERSED_ENTRY not in result.error_codes

        debit_feedback = [
            item for item in result.feedback if item.component == FeedbackComponent.DEBIT_ACCOUNT
        ]
        assert len(debit_feedback) == 1
        assert debit_feedback[0].kind == FeedbackKind.HINT
        assert debit_feedback[0].code is None


def test_wrong_credit_account_without_reversal_stays_hint_across_attempts():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), credit_account="2000")

    for attempt_number in (1, 2, 5):
        result = diagnose(problem, attempt, attempt_number=attempt_number)

        assert DiagnosticErrorCode.REVERSED_ENTRY not in result.error_codes

        credit_feedback = [
            item for item in result.feedback if item.component == FeedbackComponent.CREDIT_ACCOUNT
        ]
        assert len(credit_feedback) == 1
        assert credit_feedback[0].kind == FeedbackKind.HINT
        assert credit_feedback[0].code is None


def test_wrong_entry_amount_stays_hint_across_attempts():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), entry_amount=Decimal("9999"))

    for attempt_number in (1, 2, 5):
        result = diagnose(problem, attempt, attempt_number=attempt_number)

        entry_feedback = [
            item for item in result.feedback if item.component == FeedbackComponent.ENTRY_AMOUNT
        ]
        assert len(entry_feedback) == 1
        assert entry_feedback[0].kind == FeedbackKind.HINT
        assert entry_feedback[0].code is None


def test_wrong_carrying_amount_stays_hint_across_attempts():
    problem = _direct_problem()
    attempt = replace(_correct_attempt(), carrying_amount=Decimal("9999"))

    for attempt_number in (1, 2, 5):
        result = diagnose(problem, attempt, attempt_number=attempt_number)

        carrying_feedback = [
            item
            for item in result.feedback
            if item.component == FeedbackComponent.CARRYING_AMOUNT
        ]
        assert len(carrying_feedback) == 1
        assert carrying_feedback[0].kind == FeedbackKind.HINT
        assert carrying_feedback[0].code is None
