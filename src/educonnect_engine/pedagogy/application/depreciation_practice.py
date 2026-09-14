"""AMO-001 end-to-end practice workflow.

Orchestrates the existing building blocks — the problem generator, the
exercise builder, `DiagnosticEngine.diagnose()`, and the direct/indirect
method comparison — into one in-memory practice session:

    Application -> Generator -> Exercise builder -> Accounting truth
    Application -> DiagnosticEngine -> Accounting truth
    Application -> Method comparison -> Accounting truth

This module never recalculates depreciation, never re-derives a diagnosis,
and never rebuilds correction text: it only sequences calls to the existing
domain functions and owns the attempt-number bookkeeping, so callers cannot
manipulate the pedagogical feedback level by supplying their own number.

The session moves through three distinct phases, tracked explicitly so the
state can never be ambiguous:

    ACCOUNTING   -- learner submits journal/calculation attempts.
    COMPARISON   -- accounting attempts are closed; the direct/indirect
                    comparison is unlocked and can be submitted.
    COMPLETED    -- the practice is finished: the model answer and the full
                    commented correction (which itself explains direct vs
                    indirect) become visible, and only then.

Completing the accounting phase never exposes the model answer or the
correction, and finishing is only reachable after at least one comparison
attempt — so the correction cannot leak the comparison's own answer before
the learner has engaged with it. A comparison attempt does not need to be
fully correct to allow finishing: completion and mastery are different
concerns.

No persistence, no repositories, no user/session database concepts: the
session is a plain in-memory object for this slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from educonnect_engine.accounting.depreciation import DepreciationProblem
from educonnect_engine.pedagogy.domain.diagnostics import (
    DiagnosticResult,
    LearnerAttempt,
    diagnose,
)
from educonnect_engine.pedagogy.domain.exercise import (
    CommentedCorrection,
    DepreciationExercise,
    ExpectedAnswer,
    build_depreciation_exercise,
)
from educonnect_engine.pedagogy.domain.generator import generate_depreciation_problem
from educonnect_engine.pedagogy.domain.method_comparison import (
    ComparisonAttempt,
    ComparisonResult,
    DepreciationMethodComparison,
    build_method_comparison,
    verify_comparison_attempt,
)


class PracticePhase(StrEnum):
    """The three distinct, mutually exclusive stages of one practice session."""

    ACCOUNTING = "accounting"
    COMPARISON = "comparison"
    COMPLETED = "completed"


class AccountingPhaseClosedError(Exception):
    """Raised when an accounting attempt is submitted after that phase closed."""


class ComparisonPhaseNotUnlockedError(Exception):
    """Raised when the comparison is accessed before the accounting phase closes."""


class ComparisonNotAttemptedError(Exception):
    """Raised when `finish()` is called before a comparison attempt was submitted."""


@dataclass(frozen=True, slots=True)
class LearnerFacingExercise:
    """The pre-finish exercise view exposed to the learner.

    Structurally cannot carry the solution: it has no `expected_answer` or
    `correction` field at all, by design.
    """

    problem: DepreciationProblem
    prompt: str
    economic_rationale: str


@dataclass(frozen=True, slots=True)
class CompletedDepreciationPractice:
    """The post-finish view: the model answer and the full correction."""

    problem: DepreciationProblem
    expected_answer: ExpectedAnswer
    correction: CommentedCorrection


@dataclass(slots=True)
class DepreciationPracticeSession:
    """One in-memory AMO-001 practice session for a single generated problem."""

    problem: DepreciationProblem
    exercise: DepreciationExercise
    attempt_number: int = field(default=0)
    phase: PracticePhase = field(default=PracticePhase.ACCOUNTING)
    comparison_attempted: bool = field(default=False)

    @classmethod
    def start(cls, seed: int) -> DepreciationPracticeSession:
        """Generate a problem from `seed` and build its exercise.

        No randomness happens anywhere else in this workflow.
        """
        problem = generate_depreciation_problem(seed)
        exercise = build_depreciation_exercise(problem)
        return cls(problem=problem, exercise=exercise)

    @property
    def learner_view(self) -> LearnerFacingExercise:
        """The learner-safe view: prompt, rationale, and problem data, never the solution."""
        return LearnerFacingExercise(
            problem=self.problem,
            prompt=self.exercise.prompt,
            economic_rationale=self.exercise.economic_rationale,
        )

    def submit(self, attempt: LearnerAttempt) -> DiagnosticResult:
        """Diagnose one learner attempt against this session's problem.

        Only allowed during the ACCOUNTING phase. The session owns
        attempt-number sequencing (1, 2, 3, ...); it is never accepted from
        the caller.
        """
        if self.phase is not PracticePhase.ACCOUNTING:
            raise AccountingPhaseClosedError(
                "cannot submit an accounting attempt after the accounting phase has closed"
            )
        self.attempt_number += 1
        return diagnose(self.problem, attempt, attempt_number=self.attempt_number)

    def complete_accounting_phase(self) -> None:
        """Close accounting attempts and unlock the direct/indirect comparison.

        Does not expose the expected answer or the correction — those only
        become available from `finish()`, after a comparison attempt.
        """
        if self.phase is not PracticePhase.ACCOUNTING:
            raise AccountingPhaseClosedError("the accounting phase is already closed")
        self.phase = PracticePhase.COMPARISON

    @property
    def comparison(self) -> DepreciationMethodComparison:
        """The DIRECT vs INDIRECT comparison table, available once the accounting phase closes.

        Built from `method_comparison.build_method_comparison()`, which in
        turn only calls `accounting.solve()` — no accounting rule is
        reimplemented here.
        """
        if self.phase is PracticePhase.ACCOUNTING:
            raise ComparisonPhaseNotUnlockedError(
                "complete the accounting phase before starting the method comparison"
            )
        return build_method_comparison(self.problem)

    def submit_comparison(self, attempt: ComparisonAttempt) -> ComparisonResult:
        """Verify a learner's direct/indirect comparison attempt.

        Delegates entirely to `method_comparison.verify_comparison_attempt()`;
        this session never re-derives comparison correctness itself. The
        attempt does not need to be fully correct to unlock `finish()`.
        """
        result = verify_comparison_attempt(self.comparison, attempt)
        self.comparison_attempted = True
        return result

    def finish(self) -> CompletedDepreciationPractice:
        """Expose the model answer and the full correction.

        Only reachable after at least one comparison attempt, so the
        correction — which itself explains direct vs indirect — cannot leak
        that answer before the learner has engaged with the comparison.
        Both are copied verbatim from the exercise built at `start()` time —
        never rebuilt or recalculated here.
        """
        if not self.comparison_attempted:
            raise ComparisonNotAttemptedError(
                "submit a comparison attempt before finishing the practice"
            )
        self.phase = PracticePhase.COMPLETED
        return CompletedDepreciationPractice(
            problem=self.problem,
            expected_answer=self.exercise.expected_answer,
            correction=self.exercise.correction,
        )
