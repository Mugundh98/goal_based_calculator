"""Monte Carlo over a whole lifetime: save until retirement, then live off the corpus.

Accumulation (n years) is the Phase 5 engine's recursion with the pre-retirement return. The
withdrawal phase (m years) runs on the same paths with the post-retirement return:

    V_{t+1} = (V_t - W_t) x e^{R_t},   V_0 = corpus at retirement,
    W_t = first monthly withdrawal x (1 + inflation)^(t // 12)   (start of month, as Phase 3)

It also has a closed form. With D_t = e^{R_0 + ... + R_{t-1}} (growth since retirement, D_0 = 1):

    V_t = D_t x (V_0 - sum_{s<t} W_s / D_s)

The bracket is the corpus minus the present value (at retirement, along this path) of the
withdrawals made so far. It only falls, so the money runs out at the first month whose
withdrawal takes it below zero, and it lasts for life exactly when

    corpus >= C_p = sum over all m x 12 months of W_s / D_s    (the corpus THIS path needs).

The corpus at retirement is linear in the SIP (Phase 5: A + SIP x B), so the SIP that makes a
share q of the paths last is the q-quantile of (C_p - A_p) / B_p, and the corpus that does is the
q-quantile of C_p - both exact, from one run. Returns follow ADR-008: the expected return is the
median growth rate, the model supplies centred shocks, and zero volatility reproduces
finance.retirement.plan_retirement exactly.
"""

import math
from dataclasses import dataclass

import numpy as np

from app.finance import retirement as plan_math
from app.finance.retirement import RetirementInputs
from app.simulation import engine
from app.simulation.models import ReturnModel

MONTHS = engine.MONTHS
PERCENTILES = engine.PERCENTILES
SUCCESS_LEVELS = engine.SUCCESS_LEVELS
TOLERANCE = engine.TOLERANCE


@dataclass(frozen=True)
class LifetimeBand:
    year: int  # years from now
    age: int  # age at the end of that year
    percentiles: dict[int, float]  # balance P10 .. P90 (0 once the money has run out)
    deterministic: float  # the single-return plan


@dataclass(frozen=True)
class RetirementOutcome:
    paths: int
    success_probability: float  # share of paths whose money lasts until life expectancy
    corpus_percentiles: dict[int, float]  # value at retirement
    corpus_target: float  # single-return corpus needed (finance.retirement)
    survival: list[tuple[int, float]]  # (age, share of paths with money left at that age)
    depletion_age_p10: float  # 1 in 10 paths have run out by this age (life expectancy: never)
    median_depletion_age: float | None  # among the paths that run out (None: none do)
    required_sip: dict[int, float]  # success level (%) -> starting SIP, whole rupees
    corpus_needed: dict[int, float]  # success level (%) -> corpus at retirement, whole rupees
    bands: list[LifetimeBand]


def _quantile_up(values: np.ndarray, level: float) -> float:
    """Smallest whole-rupee amount reaching at least `level` of the paths (as Phase 5)."""
    return float(math.ceil(max(float(np.quantile(values, level, method="inverted_cdf")), 0.0)))


def run(
    plan: RetirementInputs,
    pre_model: ReturnModel,
    post_model: ReturnModel,
    paths: int = engine.DEFAULT_PATHS,
    seed: int = engine.DEFAULT_SEED,
) -> RetirementOutcome:
    if paths < 1:
        raise ValueError("need at least one path")
    n, m = plan.years_to_retirement, plan.retirement_years
    rng = np.random.default_rng(seed)

    # --- Accumulation: the Phase 5 engine's closed form -----------------------------------------
    log_returns = pre_model.shocks(rng, paths, n * MONTHS)
    log_returns += math.log1p(plan.pre_retirement_return) / MONTHS
    growth, per_rupee_sip = engine.year_end_components(log_returns, plan.step_up_rate)
    del log_returns
    saving = plan.current_savings * growth + plan.monthly_sip * per_rupee_sip  # (paths, n)
    savings_part = plan.current_savings * growth[:, -1]  # A_p
    sip_part = per_rupee_sip[:, -1]  # B_p
    corpus = saving[:, -1]

    # --- Withdrawal phase -----------------------------------------------------------------------
    months = m * MONTHS
    first = plan_math.first_monthly_withdrawal(plan)
    withdrawals = first * (1 + plan.inflation_rate) ** (np.arange(months) // MONTHS)
    growth_after = post_model.shocks(rng, paths, months)
    growth_after += math.log1p(plan.post_retirement_return) / MONTHS
    np.cumsum(growth_after, axis=1, out=growth_after)
    np.exp(growth_after, out=growth_after)  # D_{t+1}: growth to the END of month t
    spent = np.empty_like(growth_after)  # becomes sum_{s<=t} W_s / D_s
    spent[:, 0] = 1.0
    spent[:, 1:] = growth_after[:, :-1]  # D_t: growth before month t's withdrawal
    np.divide(withdrawals, spent, out=spent)
    np.cumsum(spent, axis=1, out=spent)

    needed = spent[:, -1]  # C_p: the corpus this path needs
    left = corpus[:, None] - spent  # (paths, months), falls month by month
    del spent
    ran_out = left < -TOLERANCE
    lasts = ~ran_out[:, -1]
    year_ends = slice(MONTHS - 1, None, MONTHS)
    spending = np.maximum(left[:, year_ends], 0.0) * growth_after[:, year_ends]  # (paths, m)
    del growth_after, left

    first_short = np.where(lasts, months, ran_out.argmax(axis=1))  # month of the failed payment
    depletion_age = plan.retirement_age + first_short / MONTHS  # life expectancy if it lasts
    survival = [(plan.retirement_age, 1.0)] + [
        (plan.retirement_age + year, float(np.mean(~ran_out[:, year * MONTHS - 1])))
        for year in range(1, m + 1)
    ]
    del ran_out

    # --- Summaries ------------------------------------------------------------------------------
    deterministic = plan_math.plan_retirement(plan)
    values = np.concatenate([saving, spending], axis=1)  # (paths, n + m)
    by_year = np.percentile(values, PERCENTILES, axis=0)
    bands = [
        LifetimeBand(
            0,
            plan.current_age,
            {p: plan.current_savings for p in PERCENTILES},
            deterministic.lifetime[0].balance,
        ),
        *(
            LifetimeBand(
                year,
                plan.current_age + year,
                {p: float(by_year[i, year - 1]) for i, p in enumerate(PERCENTILES)},
                deterministic.lifetime[year].balance,
            )
            for year in range(1, n + m + 1)
        ),
    ]
    failed = depletion_age[~lasts]
    return RetirementOutcome(
        paths=paths,
        success_probability=float(lasts.mean()),
        corpus_percentiles={
            p: float(v)
            for p, v in zip(PERCENTILES, np.percentile(corpus, PERCENTILES), strict=True)
        },
        corpus_target=deterministic.corpus_needed,
        survival=survival,
        depletion_age_p10=float(np.quantile(depletion_age, 0.10, method="inverted_cdf")),
        median_depletion_age=float(np.median(failed)) if failed.size else None,
        required_sip={
            level: _quantile_up((needed - savings_part) / sip_part, level / 100)
            for level in SUCCESS_LEVELS
        },
        corpus_needed={level: _quantile_up(needed, level / 100) for level in SUCCESS_LEVELS},
        bands=bands,
    )
