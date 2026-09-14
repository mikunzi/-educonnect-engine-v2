"""Pedagogy domain layer."""

from .diagnostics import (
    DiagnosticErrorCode,
    DiagnosticResult,
    FeedbackComponent,
    FeedbackItem,
    FeedbackKind,
    LearnerAttempt,
    diagnose,
)
from .exercise import (
    CalculationStep,
    CommentedCorrection,
    DepreciationExercise,
    ExpectedAnswer,
    build_depreciation_exercise,
)
from .generator import (
    ACQUISITION_VALUES,
    RATES,
    SCENARIO_TEMPLATES,
    ScenarioTemplate,
    generate_depreciation_problem,
)
from .method_comparison import (
    ComparisonAttempt,
    ComparisonComponent,
    ComparisonResult,
    DepreciationMethodComparison,
    MethodPresentation,
    build_method_comparison,
    verify_comparison_attempt,
)

__all__ = [
    "ACQUISITION_VALUES",
    "RATES",
    "SCENARIO_TEMPLATES",
    "CalculationStep",
    "CommentedCorrection",
    "ComparisonAttempt",
    "ComparisonComponent",
    "ComparisonResult",
    "DepreciationExercise",
    "DepreciationMethodComparison",
    "DiagnosticErrorCode",
    "DiagnosticResult",
    "ExpectedAnswer",
    "FeedbackComponent",
    "FeedbackItem",
    "FeedbackKind",
    "LearnerAttempt",
    "MethodPresentation",
    "ScenarioTemplate",
    "build_depreciation_exercise",
    "build_method_comparison",
    "diagnose",
    "generate_depreciation_problem",
    "verify_comparison_attempt",
]
