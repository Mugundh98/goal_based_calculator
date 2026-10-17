"""Return-model comparison: the chance of success of sample goals under the 4 return models.

Each sample goal is given exactly the SIP the single-return plan (Phase 3) says is enough, then
simulated with the normal, block-bootstrap, GARCH(1,1) and regime-switching (HMM) models on the
same 10,000 paths' seed. "On paper the plan works; how often does it really?"
"""

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.evaluation.report import table
from app.finance.goal_plan import GoalInputs, project_goal
from app.models import Goal
from app.schemas.simulation import ComparisonRequest, SimulationOverrides
from app.services import simulations as simulation_service

MODEL_LABELS = {
    "normal": "Normal",
    "bootstrap": "Block bootstrap",
    "garch": "GARCH(1,1)",
    "hmm": "Regime-switching (HMM)",
}


@dataclass(frozen=True)
class SampleGoal:
    name: str
    cost_today: float
    years: int
    equity_percent: float  # sets the assumed return (13% equity / 7% debt blend, Phase 5)


SAMPLES = (
    SampleGoal("Car, 3 years, conservative", 800_000, 3, 30),
    SampleGoal("House deposit, 7 years, moderate", 2_000_000, 7, 60),
    SampleGoal("Education, 10 years, moderate", 2_500_000, 10, 60),
    SampleGoal("Education, 15 years, aggressive", 2_500_000, 15, 85),
    SampleGoal("Wealth, 25 years, aggressive", 10_000_000, 25, 85),
)


def _goal(sample: SampleGoal, today: date) -> tuple[Goal, float]:
    """A transient goal (never saved) whose SIP is the plan's required SIP."""
    rate = simulation_service.return_for_equity_share(sample.equity_percent / 100)
    projection = project_goal(
        GoalInputs(target_today=sample.cost_today, years=sample.years, inflation_rate=0.06,
                   expected_return=rate)
    )  # fmt: skip
    sip = float(math.ceil(projection.required_sip or 0))
    goal = Goal(
        name=sample.name, goal_type="other", target_amount=Decimal(str(sample.cost_today)),
        target_year=today.year + sample.years, inflation_rate=Decimal(6), expected_return=None,
        current_savings=Decimal(0), monthly_sip=Decimal(str(sip)), step_up_rate=Decimal(0),
    )  # fmt: skip
    return goal, sip


def build(db: Session, today: date | None = None) -> tuple[str, dict[str, Any]]:
    today = today or date.today()
    nobody = SimpleNamespace(id=-1)  # no risk profile: the overrides fix the allocation
    results: list[dict[str, Any]] = []
    for sample in SAMPLES:
        goal, sip = _goal(sample, today)
        request = ComparisonRequest(
            overrides=SimulationOverrides(equity_percent=Decimal(str(sample.equity_percent)))
        )
        out = simulation_service.compare_models(db, nobody, goal, request, today)  # type: ignore[arg-type]
        results.append(
            {
                "goal": sample.name,
                "years": sample.years,
                "equity_percent": sample.equity_percent,
                "expected_return": out.inputs.expected_return,
                "inflated_target": out.inputs.inflated_target,
                "monthly_sip": sip,
                "models": {
                    m.model: {
                        "success": m.success_probability,
                        "sip_for_90": m.required_sip_90,
                        "volatility": m.annual_volatility,
                        "median_final": m.final.p50,
                        "p10_final": m.final.p10,
                    }
                    for m in out.models
                },
                "history": out.history.model_dump(mode="json") if out.history else None,
            }
        )
    names = list(results[0]["models"]) if results else []
    chance_rows = [
        [r["goal"], f"{r['equity_percent']:g}%", f"{r['expected_return']:g}%",
         f"Rs {r['monthly_sip']:,.0f}", *(r["models"][n]["success"] for n in names)]
        for r in results
    ]  # fmt: skip
    sip_rows = [
        [r["goal"], f"Rs {r['monthly_sip']:,.0f}",
         *(f"Rs {r['models'][n]['sip_for_90']:,.0f}" for n in names)]
        for r in results
    ]  # fmt: skip
    vol_rows = [[r["goal"], *(r["models"][n]["volatility"] for n in names)] for r in results]
    spreads = [
        max(r["models"][n]["success"] for n in names)
        - min(r["models"][n]["success"] for n in names)
        for r in results
    ]
    history = results[0]["history"] if results else None
    labels = [MODEL_LABELS.get(n, n) for n in names]
    md = f"""
# Return-model comparison

_Generated {today.isoformat()}. 10,000 paths per model, same seed; market data
{history["start"] if history else "-"} to {history["end"] if history else "-"}
({history["months"] if history else 0} months)._

Each goal gets the monthly SIP that the single-return plan says is exactly enough (inflation 6%,
return from the equity share: 13% equity / 7% debt). Then each return model simulates it.

## Chance of reaching the target (%)

{table(["Goal", "Equity", "Assumed return", "SIP (plan)", *labels], chance_rows)}

## SIP needed for a 90% chance

{table(["Goal", "SIP (plan)", *labels], sip_rows)}

## Simulated portfolio volatility (% a year)

{table(["Goal", *labels], vol_rows)}

## What this shows

- A SIP that meets the target "on paper" succeeds only about half the time: the plan uses the
  median return (ADR-008), so roughly half the paths end above the target and half below.
- The models agree within {min(spreads):.1f} to {max(spreads):.1f} percentage points on the chance
  of success; they differ more in the tails (the 10th percentile and the SIP for 90%), where fat
  tails, volatility clustering and crisis regimes matter.
- The SIP for a 90% chance is the practical number: certainty costs more for equity-heavy and
  long goals, because their outcomes spread wider.
"""
    return md, {"generated": today.isoformat(), "goals": results}
