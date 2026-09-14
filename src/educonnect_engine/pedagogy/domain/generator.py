"""Deterministic AMO-001 depreciation problem generator."""

from dataclasses import dataclass
from decimal import Decimal
from random import Random

from educonnect_engine.accounting.depreciation import (
    FURNITURE,
    IT_EQUIPMENT,
    MACHINE,
    VEHICLE,
    AccountingMethod,
    DepreciableAsset,
    DepreciationProblem,
)

ACQUISITION_VALUES: tuple[Decimal, ...] = (
    Decimal("24000"),
    Decimal("30000"),
    Decimal("36000"),
    Decimal("48000"),
    Decimal("60000"),
    Decimal("75000"),
    Decimal("80000"),
    Decimal("100000"),
)

RATES: tuple[Decimal, ...] = (
    Decimal("0.10"),
    Decimal("0.125"),
    Decimal("0.20"),
    Decimal("0.25"),
)

_ACCOUNTING_METHODS: tuple[AccountingMethod, ...] = (
    AccountingMethod.DIRECT,
    AccountingMethod.INDIRECT,
)

_EXERCISE_YEAR = 2026


@dataclass(frozen=True, slots=True)
class ScenarioTemplate:
    """A professional context bound to the one asset it makes sense with.

    Context and asset are never selected independently: only a whole
    template is picked, so an incompatible pairing (e.g. a fiduciary office
    depreciating a vehicle) can never be generated.
    """

    context: str
    asset: DepreciableAsset


SCENARIO_TEMPLATES: tuple[ScenarioTemplate, ...] = (
    ScenarioTemplate(context="Atelier de menuiserie Alpina Menuiserie Sàrl", asset=MACHINE),
    ScenarioTemplate(context="Cabinet fiduciaire Fiduco Sàrl", asset=IT_EQUIPMENT),
    ScenarioTemplate(context="Entreprise de transport Transalpine SA", asset=VEHICLE),
    ScenarioTemplate(context="Restaurant Le Trèfle Sàrl", asset=FURNITURE),
)


def generate_depreciation_problem(seed: int) -> DepreciationProblem:
    """Deterministically generate a valid AMO-001 depreciation problem.

    Draws from a local `random.Random(seed)` only — the global `random`
    module state is never touched — so the same seed always reproduces the
    exact same problem, independent of call order or other code's random use.
    """
    rng = Random(seed)

    scenario = rng.choice(SCENARIO_TEMPLATES)
    acquisition_value = rng.choice(ACQUISITION_VALUES)
    rate = rng.choice(RATES)
    accounting_method = rng.choice(_ACCOUNTING_METHODS)

    return DepreciationProblem(
        acquisition_value=acquisition_value,
        rate=rate,
        accounting_method=accounting_method,
        asset=scenario.asset,
        exercise_year=_EXERCISE_YEAR,
        context=scenario.context,
    )
