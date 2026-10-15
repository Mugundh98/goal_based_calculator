"""Goal planning: turns one goal into an inflation-adjusted target and a required SIP.

Built only from the formulas in tvm.py. Pure: no database, no HTTP.

Expected return assumptions (until Phase 8 derives them from a real asset allocation):

| Risk category  | Assumed annual return |
|----------------|-----------------------|
| conservative   | 8%                    |
| moderate       | 10%  (also used when there is no risk profile yet) |
| aggressive     | 12%                   |
| any, goal < 3 years away | 7% - money needed soon should not sit in equity |
"""

import math
from dataclasses import dataclass
from typing import Literal

from app.finance import tvm

RETURN_BY_CATEGORY = {"conservative": 0.08, "moderate": 0.10, "aggressive": 0.12}
DEFAULT_CATEGORY = "moderate"
SHORT_HORIZON_YEARS = 3
SHORT_HORIZON_RETURN = 0.07

ReturnSource = Literal["custom", "risk_profile", "short_horizon", "default"]


def suggested_return(category: str | None, years: int) -> tuple[float, ReturnSource]:
    """Assumed annual return for a goal, and where the number came from."""
    if years < SHORT_HORIZON_YEARS:
        return SHORT_HORIZON_RETURN, "short_horizon"
    if category in RETURN_BY_CATEGORY:
        return RETURN_BY_CATEGORY[category], "risk_profile"
    return RETURN_BY_CATEGORY[DEFAULT_CATEGORY], "default"


@dataclass(frozen=True)
class GoalInputs:
    target_today: float  # cost of the goal in today's rupees
    years: int  # whole years until the goal
    inflation_rate: float  # fraction per year
    expected_return: float  # fraction per year
    current_savings: float = 0.0  # already set aside for this goal
    monthly_sip: float = 0.0  # currently invested each month for this goal
    step_up_rate: float = 0.0  # yearly increase of the SIP, fraction


@dataclass(frozen=True)
class GoalProjection:
    years_to_goal: int
    inflated_target: float  # what the goal will cost in its target year
    savings_value: float  # current savings grown to the target year
    sip_value: float  # the planned SIP grown to the target year
    projected_value: float  # savings_value + sip_value
    shortfall: float  # how much is still missing (0 if on track)
    required_sip: float | None  # starting SIP, whole rupees (None: goal is due and still short)
    funded_percent: float  # projected / target, capped at 100
    on_track: bool
    real_return: float  # expected return after inflation


def project_goal(goal: GoalInputs) -> GoalProjection:
    years = max(goal.years, 0)
    months = years * tvm.MONTHS_PER_YEAR

    target = tvm.inflate(goal.target_today, goal.inflation_rate, years)
    savings_value = tvm.future_value(goal.current_savings, goal.expected_return, years)
    if goal.step_up_rate:
        sip_value = tvm.step_up_sip_future_value(
            goal.monthly_sip, goal.expected_return, years, goal.step_up_rate
        )
    else:
        sip_value = tvm.sip_future_value(goal.monthly_sip, goal.expected_return, months)
    projected = savings_value + sip_value
    shortfall = max(target - projected, 0.0)

    required: float | None
    if savings_value >= target:
        required = 0.0
    elif years == 0:
        required = None  # no months left to invest
    elif goal.step_up_rate:
        required = tvm.required_step_up_sip(
            target, goal.expected_return, years, goal.step_up_rate, goal.current_savings
        )
    else:
        required = tvm.required_sip(target, goal.expected_return, months, goal.current_savings)

    # Round towards safety: a SIP rounded DOWN would leave the goal a few rupees short, and a
    # progress bar rounded UP would show 100% for a goal that is not quite reached.
    funded = math.floor(projected / target * 1000) / 10 if target > 0 else 100.0
    return GoalProjection(
        years_to_goal=years,
        inflated_target=round(target, 2),
        savings_value=round(savings_value, 2),
        sip_value=round(sip_value, 2),
        projected_value=round(projected, 2),
        shortfall=round(shortfall, 2),
        required_sip=None if required is None else float(math.ceil(required)),
        funded_percent=min(funded, 100.0),
        # Half a rupee of tolerance so rounding never flips the status.
        on_track=shortfall < 0.5,
        real_return=round(tvm.real_return(goal.expected_return, goal.inflation_rate), 6),
    )
