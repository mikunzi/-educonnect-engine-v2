"""Depreciation (amortissement) exercises: compute and book one year of depreciation."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AccountingMethod(StrEnum):
    """Method used to record depreciation in the general ledger."""

    DIRECT = "direct"
    INDIRECT = "indirect"


@dataclass(frozen=True, slots=True)
class DepreciableAsset:
    """An asset class eligible for depreciation, with its ledger accounts."""

    name: str
    asset_account: str
    expense_account: str
    correction_account: str | None = None

    def __post_init__(self) -> None:
        """Validate basic structural constraints."""
        if not self.name.strip():
            raise ValueError("name must not be empty")


MACHINE = DepreciableAsset(
    name="Machines",
    asset_account="1500",
    expense_account="6800",
    correction_account="1509",
)

FURNITURE = DepreciableAsset(
    name="Mobilier",
    asset_account="1510",
    expense_account="6800",
    correction_account="1519",
)

IT_EQUIPMENT = DepreciableAsset(
    name="Équipement informatique",
    asset_account="1520",
    expense_account="6800",
    correction_account="1529",
)

VEHICLE = DepreciableAsset(
    name="Véhicules",
    asset_account="1530",
    expense_account="6800",
    correction_account="1539",
)


@dataclass(frozen=True, slots=True)
class DepreciationProblem:
    """A depreciation exercise for one asset over one exercise year."""

    acquisition_value: Decimal
    rate: Decimal
    accounting_method: AccountingMethod
    asset: DepreciableAsset
    exercise_year: int
    context: str

    def __post_init__(self) -> None:
        """Validate basic structural constraints."""
        if self.acquisition_value <= 0:
            raise ValueError("acquisition_value must be positive")
        if self.rate <= 0:
            raise ValueError("rate must be positive")
        if self.rate >= 1:
            raise ValueError("rate must be less than 1")
        if not self.context.strip():
            raise ValueError("context must not be empty")
        if (
            self.accounting_method is AccountingMethod.INDIRECT
            and self.asset.correction_account is None
        ):
            raise ValueError(
                "indirect depreciation requires the asset to have a correction-of-value account"
            )


@dataclass(frozen=True, slots=True)
class DepreciationSolution:
    """The computed depreciation entry for a `DepreciationProblem`."""

    depreciation_amount: Decimal
    carrying_amount: Decimal
    debit_account: str
    credit_account: str
    entry_amount: Decimal


def solve(problem: DepreciationProblem) -> DepreciationSolution:
    """Compute one year of straight-line depreciation on acquisition cost.

    The direct method credits the asset account itself; the indirect method
    credits the asset's value-correction (contra-asset) account instead.
    """
    depreciation_amount = problem.acquisition_value * problem.rate
    carrying_amount = problem.acquisition_value - depreciation_amount

    if problem.accounting_method is AccountingMethod.DIRECT:
        credit_account = problem.asset.asset_account
    else:
        assert problem.asset.correction_account is not None
        credit_account = problem.asset.correction_account

    return DepreciationSolution(
        depreciation_amount=depreciation_amount,
        carrying_amount=carrying_amount,
        debit_account=problem.asset.expense_account,
        credit_account=credit_account,
        entry_amount=depreciation_amount,
    )
