"""Diagnostics for learner attempts at depreciation exercises (AMO-001)."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from educonnect_engine.accounting.depreciation import (
    DepreciationProblem,
    DepreciationSolution,
    solve,
)


class DiagnosticErrorCode(StrEnum):
    """Pedagogical error codes identified in a learner's attempt."""

    VCN_INSTEAD_OF_DEPRECIATION = "vcn_instead_of_depreciation"
    REVERSED_ENTRY = "reversed_entry"


class FeedbackKind(StrEnum):
    """The pedagogical intent of a feedback item."""

    CORRECT = "correct"
    HINT = "hint"
    EXPLANATION = "explanation"


class FeedbackComponent(StrEnum):
    """The answer component a feedback item is about."""

    OVERALL = "overall"
    DEPRECIATION_AMOUNT = "depreciation_amount"
    JOURNAL_ENTRY = "journal_entry"
    DEBIT_ACCOUNT = "debit_account"
    CREDIT_ACCOUNT = "credit_account"
    ENTRY_AMOUNT = "entry_amount"
    CARRYING_AMOUNT = "carrying_amount"


@dataclass(frozen=True, slots=True)
class FeedbackItem:
    """One piece of structured, component-specific feedback."""

    component: FeedbackComponent
    kind: FeedbackKind
    code: DiagnosticErrorCode | None
    message: str


@dataclass(frozen=True, slots=True)
class LearnerAttempt:
    """What the learner entered for a depreciation exercise."""

    depreciation_amount: Decimal
    debit_account: str
    credit_account: str
    entry_amount: Decimal
    carrying_amount: Decimal


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    """The pedagogical error codes, component score, and feedback for a learner's attempt."""

    error_codes: frozenset[DiagnosticErrorCode]
    score: int
    max_score: int
    feedback: tuple[FeedbackItem, ...]


_DEPRECIATION_AMOUNT_POINTS = 4
_DEBIT_ACCOUNT_POINTS = 2
_CREDIT_ACCOUNT_POINTS = 2
_ENTRY_AMOUNT_POINTS = 1
_CARRYING_AMOUNT_POINTS = 1
_MAX_SCORE = (
    _DEPRECIATION_AMOUNT_POINTS
    + _DEBIT_ACCOUNT_POINTS
    + _CREDIT_ACCOUNT_POINTS
    + _ENTRY_AMOUNT_POINTS
    + _CARRYING_AMOUNT_POINTS
)


def _depreciation_amount_feedback(
    attempt: LearnerAttempt,
    error_codes: frozenset[DiagnosticErrorCode],
    attempt_number: int,
) -> FeedbackItem:
    """Feedback for the depreciation_amount component, gated by attempt number.

    A first incorrect attempt only gets a targeted hint; the full explanation
    (naming the entered value) is only given from the second attempt on.
    """
    if DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION not in error_codes:
        return FeedbackItem(
            component=FeedbackComponent.DEPRECIATION_AMOUNT,
            kind=FeedbackKind.HINT,
            code=None,
            message=(
                "Le montant de l'amortissement n'est pas correct. Recalculez-le à "
                "partir de la valeur d'acquisition et du taux."
            ),
        )

    if attempt_number == 1:
        return FeedbackItem(
            component=FeedbackComponent.DEPRECIATION_AMOUNT,
            kind=FeedbackKind.HINT,
            code=DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION,
            message=(
                "Ce montant ne correspond pas à l'amortissement attendu. Assurez-vous de "
                "ne pas confondre la charge d'amortissement de l'exercice avec la valeur "
                "comptable nette (VCN)."
            ),
        )

    return FeedbackItem(
        component=FeedbackComponent.DEPRECIATION_AMOUNT,
        kind=FeedbackKind.EXPLANATION,
        code=DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION,
        message=(
            f"Vous avez saisi {attempt.depreciation_amount}, qui correspond à la "
            "valeur comptable nette (VCN) et non à la charge d'amortissement de "
            "l'exercice."
        ),
    )


def _reversed_entry_feedback(attempt_number: int) -> FeedbackItem:
    """Feedback for a reversed journal entry, gated by attempt number.

    A first incorrect attempt only gets a hint to re-check the direction; the
    full accounting rule is only explained from the second attempt on.
    """
    if attempt_number == 1:
        return FeedbackItem(
            component=FeedbackComponent.JOURNAL_ENTRY,
            kind=FeedbackKind.HINT,
            code=DiagnosticErrorCode.REVERSED_ENTRY,
            message=(
                "Votre écriture ne semble pas correcte. Relisez la question et vérifiez "
                "le sens (débit ou crédit) de chaque compte avant de revalider."
            ),
        )

    return FeedbackItem(
        component=FeedbackComponent.JOURNAL_ENTRY,
        kind=FeedbackKind.EXPLANATION,
        code=DiagnosticErrorCode.REVERSED_ENTRY,
        message=(
            "Votre écriture semble inversée : la charge d'amortissement doit être "
            "débitée, et le compte d'actif (ou son compte de correction de valeur) "
            "doit être crédité."
        ),
    )


def _build_feedback(
    attempt: LearnerAttempt,
    solution: DepreciationSolution,
    error_codes: frozenset[DiagnosticErrorCode],
    score: int,
    attempt_number: int,
) -> tuple[FeedbackItem, ...]:
    """Build component-specific feedback, independent of the score computation."""
    items: list[FeedbackItem] = []

    if attempt.depreciation_amount != solution.depreciation_amount:
        items.append(_depreciation_amount_feedback(attempt, error_codes, attempt_number))

    if DiagnosticErrorCode.REVERSED_ENTRY in error_codes:
        items.append(_reversed_entry_feedback(attempt_number))
    else:
        if attempt.debit_account != solution.debit_account:
            items.append(
                FeedbackItem(
                    component=FeedbackComponent.DEBIT_ACCOUNT,
                    kind=FeedbackKind.HINT,
                    code=None,
                    message="Le compte porté au débit n'est pas correct, vérifiez votre écriture.",
                )
            )
        if attempt.credit_account != solution.credit_account:
            items.append(
                FeedbackItem(
                    component=FeedbackComponent.CREDIT_ACCOUNT,
                    kind=FeedbackKind.HINT,
                    code=None,
                    message="Le compte porté au crédit n'est pas correct, vérifiez votre écriture.",
                )
            )

    if attempt.entry_amount != solution.entry_amount:
        items.append(
            FeedbackItem(
                component=FeedbackComponent.ENTRY_AMOUNT,
                kind=FeedbackKind.HINT,
                code=None,
                message="Le montant de l'écriture n'est pas correct, vérifiez votre calcul.",
            )
        )
    if attempt.carrying_amount != solution.carrying_amount:
        items.append(
            FeedbackItem(
                component=FeedbackComponent.CARRYING_AMOUNT,
                kind=FeedbackKind.HINT,
                code=None,
                message=(
                    "La valeur comptable nette indiquée n'est pas correcte, vérifiez votre "
                    "calcul."
                ),
            )
        )

    if not items:
        return (
            FeedbackItem(
                component=FeedbackComponent.OVERALL,
                kind=FeedbackKind.CORRECT,
                code=None,
                message="Bravo, votre réponse est entièrement correcte.",
            ),
        )

    if score > 0:
        items.insert(
            0,
            FeedbackItem(
                component=FeedbackComponent.OVERALL,
                kind=FeedbackKind.CORRECT,
                code=None,
                message="Plusieurs éléments de votre réponse sont corrects.",
            ),
        )

    return tuple(items)


def diagnose(
    problem: DepreciationProblem,
    attempt: LearnerAttempt,
    attempt_number: int,
) -> DiagnosticResult:
    """Compare a learner's attempt against the expected solution.

    Error diagnosis and scoring are independent of `attempt_number`: they
    depend only on the attempt's content. Only feedback selection depends on
    `attempt_number` — a component only gets an explanation (rather than a
    hint) once a deterministic error code supports it *and* this is not the
    learner's first attempt.
    """
    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")

    solution = solve(problem)
    error_codes: set[DiagnosticErrorCode] = set()

    if attempt.depreciation_amount == solution.carrying_amount:
        error_codes.add(DiagnosticErrorCode.VCN_INSTEAD_OF_DEPRECIATION)

    if (
        attempt.debit_account == solution.credit_account
        and attempt.credit_account == solution.debit_account
    ):
        error_codes.add(DiagnosticErrorCode.REVERSED_ENTRY)

    score = 0
    if attempt.depreciation_amount == solution.depreciation_amount:
        score += _DEPRECIATION_AMOUNT_POINTS
    if attempt.debit_account == solution.debit_account:
        score += _DEBIT_ACCOUNT_POINTS
    if attempt.credit_account == solution.credit_account:
        score += _CREDIT_ACCOUNT_POINTS
    if attempt.entry_amount == solution.entry_amount:
        score += _ENTRY_AMOUNT_POINTS
    if attempt.carrying_amount == solution.carrying_amount:
        score += _CARRYING_AMOUNT_POINTS

    frozen_error_codes = frozenset(error_codes)

    return DiagnosticResult(
        error_codes=frozen_error_codes,
        score=score,
        max_score=_MAX_SCORE,
        feedback=_build_feedback(attempt, solution, frozen_error_codes, score, attempt_number),
    )
