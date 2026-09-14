"""Direct vs indirect side-by-side comparison for AMO-001.

Builds a same-VCN, side-by-side presentation of how the DIRECT and INDIRECT
methods each record one year of depreciation for the same problem, and lets
a learner's filled-in comparison table be verified component by component.

No new accounting formula is introduced: every numeric value here is either
copied straight from `accounting.solve()` (called once per method) or is the
problem's own given `acquisition_value`.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum

from educonnect_engine.accounting.depreciation import (
    AccountingMethod,
    DepreciationProblem,
    solve,
)


@dataclass(frozen=True, slots=True)
class MethodPresentation:
    """How one accounting method presents the asset after one year of depreciation.

    `asset_value_presented` is deliberately named for what it *is* rather
    than what it might be assumed to be: for DIRECT it is the reduced asset
    balance (the acquisition value is no longer visible), while for
    INDIRECT it happens to equal the original acquisition value.
    """

    credited_account: str
    asset_value_presented: Decimal
    adjustment_account_balance: Decimal
    carrying_amount: Decimal


@dataclass(frozen=True, slots=True)
class DepreciationMethodComparison:
    """The DIRECT and INDIRECT presentations for the same underlying problem."""

    direct: MethodPresentation
    indirect: MethodPresentation


def build_method_comparison(problem: DepreciationProblem) -> DepreciationMethodComparison:
    """Build the DIRECT vs INDIRECT comparison table for `problem`.

    Regardless of `problem.accounting_method`, both presentations are built
    from `accounting.solve()` on a DIRECT and an INDIRECT variant of the same
    acquisition value, rate, asset, and exercise year.
    """
    direct_solution = solve(replace(problem, accounting_method=AccountingMethod.DIRECT))
    indirect_solution = solve(replace(problem, accounting_method=AccountingMethod.INDIRECT))

    direct = MethodPresentation(
        credited_account=direct_solution.credit_account,
        # DIRECT credits the asset account itself, so its balance now *is*
        # the carrying amount — there is no separate adjustment account.
        asset_value_presented=direct_solution.carrying_amount,
        adjustment_account_balance=Decimal("0"),
        carrying_amount=direct_solution.carrying_amount,
    )
    indirect = MethodPresentation(
        credited_account=indirect_solution.credit_account,
        # INDIRECT leaves the asset account at the original acquisition
        # value; the depreciation only appears in the correction account.
        asset_value_presented=problem.acquisition_value,
        adjustment_account_balance=indirect_solution.depreciation_amount,
        carrying_amount=indirect_solution.carrying_amount,
    )

    return DepreciationMethodComparison(direct=direct, indirect=indirect)


class ComparisonComponent(StrEnum):
    """One cell of the learner-filled comparison table."""

    DIRECT_CREDITED_ACCOUNT = "direct_credited_account"
    INDIRECT_CREDITED_ACCOUNT = "indirect_credited_account"
    DIRECT_PRESENTED_ASSET_VALUE = "direct_presented_asset_value"
    INDIRECT_ACQUISITION_VALUE_SHOWN = "indirect_acquisition_value_shown"
    INDIRECT_ADJUSTMENT_AMOUNT = "indirect_adjustment_amount"
    DIRECT_CARRYING_AMOUNT = "direct_carrying_amount"
    INDIRECT_CARRYING_AMOUNT = "indirect_carrying_amount"


@dataclass(frozen=True, slots=True)
class ComparisonAttempt:
    """What the learner entered for the direct/indirect comparison table."""

    direct_credited_account: str
    indirect_credited_account: str
    direct_presented_asset_value: Decimal
    indirect_acquisition_value_shown: Decimal
    indirect_adjustment_amount: Decimal
    direct_carrying_amount: Decimal
    indirect_carrying_amount: Decimal


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Component-based correctness of a learner's comparison attempt."""

    correct_components: frozenset[ComparisonComponent]
    incorrect_components: frozenset[ComparisonComponent]

    @property
    def is_fully_correct(self) -> bool:
        """Whether every component of the comparison table was correct."""
        return not self.incorrect_components


def verify_comparison_attempt(
    comparison: DepreciationMethodComparison, attempt: ComparisonAttempt
) -> ComparisonResult:
    """Check each cell of `attempt` against `comparison`, independently.

    A component-based correctness result only — no pedagogical diagnosis or
    misconception inference for this closure slice.
    """
    checks: dict[ComparisonComponent, bool] = {
        ComparisonComponent.DIRECT_CREDITED_ACCOUNT: (
            attempt.direct_credited_account == comparison.direct.credited_account
        ),
        ComparisonComponent.INDIRECT_CREDITED_ACCOUNT: (
            attempt.indirect_credited_account == comparison.indirect.credited_account
        ),
        ComparisonComponent.DIRECT_PRESENTED_ASSET_VALUE: (
            attempt.direct_presented_asset_value == comparison.direct.asset_value_presented
        ),
        ComparisonComponent.INDIRECT_ACQUISITION_VALUE_SHOWN: (
            attempt.indirect_acquisition_value_shown
            == comparison.indirect.asset_value_presented
        ),
        ComparisonComponent.INDIRECT_ADJUSTMENT_AMOUNT: (
            attempt.indirect_adjustment_amount == comparison.indirect.adjustment_account_balance
        ),
        ComparisonComponent.DIRECT_CARRYING_AMOUNT: (
            attempt.direct_carrying_amount == comparison.direct.carrying_amount
        ),
        ComparisonComponent.INDIRECT_CARRYING_AMOUNT: (
            attempt.indirect_carrying_amount == comparison.indirect.carrying_amount
        ),
    }

    correct = frozenset(component for component, ok in checks.items() if ok)
    incorrect = frozenset(component for component, ok in checks.items() if not ok)

    return ComparisonResult(correct_components=correct, incorrect_components=incorrect)
