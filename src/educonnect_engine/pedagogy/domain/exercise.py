"""The complete AMO-001 pedagogical exercise package: case, model answer, correction.

This is the end-of-exercise correction, built once the learner is done. It is
a separate concern from `diagnostics.DiagnosticEngine`, which helps during an
attempt: neither module depends on the other, and `CommentedCorrection` never
depends on what a learner actually answered.

This module carries only semantic values (Decimal amounts and rates, account
numbers, French prose that never embeds a pre-formatted number). It does not
decide how those numbers are typeset for a learner — Swiss thousands
separators, fixed decimal counts, and percentage display are a presentation
concern, owned by `pedagogy.presentation.formatting`. This module never
imports from `pedagogy.presentation`.
"""

from dataclasses import dataclass
from decimal import Decimal

from educonnect_engine.accounting.depreciation import (
    AccountingMethod,
    DepreciationProblem,
    DepreciationSolution,
    solve,
)


@dataclass(frozen=True, slots=True)
class ExpectedAnswer:
    """The model answer, copied verbatim from `accounting.solve()` — never recomputed."""

    depreciation_amount: Decimal
    debit_account: str
    credit_account: str
    entry_amount: Decimal
    carrying_amount: Decimal


@dataclass(frozen=True, slots=True)
class CalculationStep:
    """One structured step of the calculation correction.

    Carries only semantic values: the two raw Decimal operands, the
    operator between them ("x" or "-"), and the raw Decimal result.
    `right_operand_is_rate` tells the presentation layer whether
    `right_operand` should be displayed as a percentage or as an amount —
    the domain does not format either itself.
    """

    left_operand: Decimal
    operator: str
    right_operand: Decimal
    right_operand_is_rate: bool
    result: Decimal
    unit: str
    explanation: str


@dataclass(frozen=True, slots=True)
class CommentedCorrection:
    """The full, end-of-exercise correction: calculation, journal entry, VCN.

    `carrying_amount_explanation_prefix`/`_suffix` are the two prose
    fragments surrounding the acquisition value in the VCN explanation; the
    presentation layer inserts the formatted amount between them (that
    sentence is the one place this correction would otherwise need to embed
    a formatted number — see `pedagogy.presentation.formatting`).
    """

    calculation_steps: tuple[CalculationStep, ...]
    accounting_explanation: str
    carrying_amount_explanation_prefix: str
    carrying_amount_explanation_suffix: str
    method_explanation: str


@dataclass(frozen=True, slots=True)
class DepreciationExercise:
    """A complete AMO-001 pedagogical triplet: case, model answer, correction."""

    problem: DepreciationProblem
    prompt: str
    economic_rationale: str
    expected_answer: ExpectedAnswer
    correction: CommentedCorrection


def _build_economic_rationale(problem: DepreciationProblem) -> str:
    """Explain why the asset must be depreciated, without revealing the solution.

    The asset category name (e.g. "Machines", "Véhicules") is grammatically
    plural for some assets and singular for others; "Le bien comptabilisé
    dans la catégorie « X »" is used as the subject so the sentence stays
    correct regardless of which asset category is involved.
    """
    return (
        f"Le bien comptabilisé dans la catégorie « {problem.asset.name} » a été utilisé "
        f"par {problem.context} durant l'exercice {problem.exercise_year}. Cette "
        "utilisation entraîne une perte de valeur du bien au fil du temps. Si le bien "
        "restait comptabilisé à sa valeur d'acquisition d'origine, le bilan "
        "surévaluerait sa valeur réelle. L'amortissement enregistre cette perte de "
        "valeur pour la période concernée."
    )


def _build_prompt(problem: DepreciationProblem) -> str:
    """Build the instruction the learner must act on.

    The problem's data (context, asset, acquisition value, rate, method,
    year) is presented once, in the structured situation block the
    presentation layer renders alongside this prompt — it is deliberately
    not repeated here.
    """
    return (
        f"Pour l'exercice {problem.exercise_year}, déterminez : "
        "1) le montant de l'amortissement annuel ; "
        "2) l'écriture comptable correspondante, en indiquant le compte à débiter et le "
        "compte à créditer ; "
        "3) la valeur comptable nette (VCN) du bien à la fin de l'exercice."
    )


def _build_calculation_steps(
    problem: DepreciationProblem, solution: DepreciationSolution
) -> tuple[CalculationStep, ...]:
    depreciation_step = CalculationStep(
        left_operand=problem.acquisition_value,
        operator="x",
        right_operand=problem.rate,
        right_operand_is_rate=True,
        result=solution.depreciation_amount,
        unit="CHF",
        explanation=(
            "L'amortissement annuel s'obtient en appliquant le taux d'amortissement à la "
            "valeur d'acquisition."
        ),
    )
    carrying_amount_step = CalculationStep(
        left_operand=problem.acquisition_value,
        operator="-",
        right_operand=solution.depreciation_amount,
        right_operand_is_rate=False,
        result=solution.carrying_amount,
        unit="CHF",
        explanation=(
            "La valeur comptable nette s'obtient en déduisant l'amortissement de "
            "l'exercice de la valeur d'acquisition."
        ),
    )
    return (depreciation_step, carrying_amount_step)


def _build_method_explanation(problem: DepreciationProblem) -> str:
    if problem.accounting_method is AccountingMethod.DIRECT:
        return (
            "Avec la méthode directe, l'amortissement est crédité directement au compte "
            "de l'actif : la valeur d'acquisition inscrite au compte de l'actif diminue "
            "elle-même du montant de l'amortissement."
        )

    return (
        "Avec la méthode indirecte, la valeur d'acquisition reste visible telle quelle au "
        "compte de l'actif ; l'amortissement est enregistré au crédit du compte "
        "d'ajustement de valeur (correction de valeur), qui vient en déduction de la "
        "valeur d'acquisition pour obtenir la valeur comptable nette."
    )


def _build_correction(
    problem: DepreciationProblem, solution: DepreciationSolution
) -> CommentedCorrection:
    accounting_explanation = (
        f"L'amortissement de l'exercice est débité au compte de charge "
        f"{solution.debit_account} et crédité au compte {solution.credit_account}."
    )

    return CommentedCorrection(
        calculation_steps=_build_calculation_steps(problem, solution),
        accounting_explanation=accounting_explanation,
        carrying_amount_explanation_prefix=(
            "La valeur comptable nette (VCN) s'obtient en soustrayant l'amortissement de "
            "l'exercice de la valeur d'acquisition ("
        ),
        carrying_amount_explanation_suffix=(
            ") : elle représente la valeur du bien encore inscrite au bilan après "
            "amortissement."
        ),
        method_explanation=_build_method_explanation(problem),
    )


def build_depreciation_exercise(problem: DepreciationProblem) -> DepreciationExercise:
    """Build the complete, deterministic AMO-001 exercise for `problem`.

    The expected answer is copied field-by-field from `accounting.solve()` —
    the pedagogy layer never recomputes the accounting formula itself.
    """
    solution = solve(problem)

    expected_answer = ExpectedAnswer(
        depreciation_amount=solution.depreciation_amount,
        debit_account=solution.debit_account,
        credit_account=solution.credit_account,
        entry_amount=solution.entry_amount,
        carrying_amount=solution.carrying_amount,
    )

    return DepreciationExercise(
        problem=problem,
        prompt=_build_prompt(problem),
        economic_rationale=_build_economic_rationale(problem),
        expected_answer=expected_answer,
        correction=_build_correction(problem, solution),
    )
