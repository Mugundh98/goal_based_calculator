"""The Monte Carlo engine: grow a goal's savings and SIPs along thousands of random paths.

For every path p and month t (t = 0 .. n-1), with R the monthly log return drawn by a model:

    V_{t+1} = (V_t + SIP_t) x e^{R_t},   V_0 = current savings

the same cash-flow rules as Phase 3 (ADR-006): the SIP is invested at the START of the month
(annuity due) and raised by the step-up rate every 12 months. The monthly log return is

    R = mu + shock,   mu = ln(1 + r) / 12

where r is the goal's expected return and the shock (mean 0) comes from the return model. mu
is the effective monthly rate of Phase 3 in log form, so with zero shocks every path is exactly
the Phase 3 projection. With shocks, r is the MEDIAN compound growth rate (ADR-008).

Vectorised: no Python loop over paths or months. The recursion has a closed form,

    V_t = G_t x (V_0 + sum_{s<t} SIP_s / G_s),   G_t = e^{R_0 + ... + R_{t-1}}

(each rupee grows by the cumulative growth since it was invested), so the whole (paths x months)
grid is two cumulative sums. The value at the goal date is linear in the SIP:

    V_n = A + SIP x B,   A = V_0 G_n,   B = sum_s k_s G_n / G_s   (k_s = step-up factor)

which gives the SIP needed for any success probability exactly, from the same paths.
"""

import math
from dataclasses import dataclass

import numpy as np

from app.finance import tvm
from app.finance.goal_plan import GoalInputs
from app.simulation.models import ReturnModel

DEFAULT_PATHS = 10_000
DEFAULT_SEED = 2026  # a fixed default: the same inputs always give the same answer
PERCENTILES = (10, 25, 50, 75, 90)
SUCCESS_LEVELS = (50, 75, 90)  # success probabilities (%) for which the required SIP is given
TOLERANCE = 0.5  # half a rupee, as Phase 3's on-track test, so rounding never decides success

MONTHS = tvm.MONTHS_PER_YEAR


@dataclass(frozen=True)
class YearBand:
    year: int  # years from now (0 = today)
    percentiles: dict[int, float]  # P10 .. P90 of the value at the end of that year
    deterministic: float  # Phase 3 projection for that year


@dataclass(frozen=True)
class SimulationOutcome:
    paths: int
    years: int
    target: float  # inflated target (Phase 3)
    success_probability: float  # fraction of paths that reach the target
    final_percentiles: dict[int, float]
    final_mean: float
    median_shortfall: float | None  # how far the missing paths miss, typically (None: none miss)
    required_sip: dict[int, float]  # success level (%) -> starting SIP in whole rupees
    bands: list[YearBand]


def contribution_schedule(step_up_rate: float, months: int) -> np.ndarray:
    """SIP of month t per rupee of starting SIP: (1 + s)^(t // 12)."""
    return (1 + step_up_rate) ** (np.arange(months) // MONTHS)


def year_end_components(
    log_returns: np.ndarray, step_up_rate: float
) -> tuple[np.ndarray, np.ndarray]:
    """For each path and year y = 1..n: growth G (of ₹1 saved today) and B (of a ₹1 SIP).

    The value of the plan at the end of year y is savings x G + SIP x B.
    """
    paths, months = log_returns.shape
    growth = np.cumsum(log_returns, axis=1)  # ln G_t, cumulative growth to the end of month t
    np.exp(growth, out=growth)
    # Each month's instalment divided by the growth before it was invested ...
    per_rupee = np.empty_like(growth)
    per_rupee[:, 0] = 1.0
    per_rupee[:, 1:] = growth[:, :-1]
    np.divide(contribution_schedule(step_up_rate, months), per_rupee, out=per_rupee)
    # ... summed up to each month, then grown to that month: G_t x sum_{s<=t} k_s / G_{s-1}.
    np.cumsum(per_rupee, axis=1, out=per_rupee)
    year_ends = slice(MONTHS - 1, None, MONTHS)
    growth_y = growth[:, year_ends]
    return growth_y, growth_y * per_rupee[:, year_ends]


def deterministic_values(goal: GoalInputs) -> list[float]:
    """Phase 3 projection at the end of each year 0..n, from the closed-form tvm formulas."""
    values = []
    for year in range(goal.years + 1):
        if goal.step_up_rate:
            sip = tvm.step_up_sip_future_value(
                goal.monthly_sip, goal.expected_return, year, goal.step_up_rate
            )
        else:
            sip = tvm.sip_future_value(goal.monthly_sip, goal.expected_return, year * MONTHS)
        values.append(tvm.future_value(goal.current_savings, goal.expected_return, year) + sip)
    return values


def required_sip(
    target: float, savings_part: np.ndarray, per_rupee_sip: np.ndarray, level: float
) -> float:
    """Smallest starting SIP (whole rupees) with which at least `level` of the paths succeed.

    Path p succeeds when A_p + SIP x B_p >= target, i.e. when SIP >= (target - A_p) / B_p. Sorting
    those per-path thresholds, the SIP at position ceil(level x paths) makes exactly that many
    paths succeed (NumPy's "inverted_cdf" quantile).
    """
    thresholds = (target - savings_part) / per_rupee_sip
    sip = float(np.quantile(thresholds, level, method="inverted_cdf"))
    return float(math.ceil(max(sip, 0.0)))


def run(
    goal: GoalInputs,
    model: ReturnModel,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
) -> SimulationOutcome:
    if goal.years < 1:
        raise tvm.FinanceInputError("the goal is due: there is no time left to simulate")
    if paths < 1:
        raise ValueError("need at least one path")
    months = goal.years * MONTHS

    rng = np.random.default_rng(seed)
    log_returns = model.shocks(rng, paths, months)
    log_returns += math.log1p(goal.expected_return) / MONTHS  # ln of Phase 3's monthly rate
    growth, per_rupee_sip = year_end_components(log_returns, goal.step_up_rate)
    del log_returns
    values = goal.current_savings * growth + goal.monthly_sip * per_rupee_sip  # (paths, years)

    target = tvm.inflate(goal.target_today, goal.inflation_rate, goal.years)
    final = values[:, -1]
    missed = target - final[final < target - TOLERANCE]
    by_year = np.percentile(values, PERCENTILES, axis=0)  # (len(PERCENTILES), years)
    deterministic = deterministic_values(goal)

    bands = [
        YearBand(0, {p: goal.current_savings for p in PERCENTILES}, deterministic[0]),
        *(
            YearBand(
                year,
                {p: float(by_year[i, year - 1]) for i, p in enumerate(PERCENTILES)},
                deterministic[year],
            )
            for year in range(1, goal.years + 1)
        ),
    ]
    return SimulationOutcome(
        paths=paths,
        years=goal.years,
        target=target,
        success_probability=float(np.mean(final >= target - TOLERANCE)),
        final_percentiles=bands[-1].percentiles,
        final_mean=float(final.mean()),
        median_shortfall=float(np.median(missed)) if missed.size else None,
        required_sip={
            level: required_sip(
                target, goal.current_savings * growth[:, -1], per_rupee_sip[:, -1], level / 100
            )
            for level in SUCCESS_LEVELS
        },
        bands=bands,
    )


def final_values_loop(
    log_returns: np.ndarray, current_savings: float, monthly_sip: float, step_up_rate: float
) -> list[float]:
    """The same simulation with plain Python loops over paths and months.

    Kept as an independent reference: the tests check the vectorised engine against it, and
    `benchmark.py` times the two.
    """
    finals = []
    for path in log_returns.tolist():
        value = current_savings
        for month, log_return in enumerate(path):
            instalment = monthly_sip * (1 + step_up_rate) ** (month // MONTHS)
            value = (value + instalment) * math.exp(log_return)
        finals.append(value)
    return finals
