"""Asset allocation per goal: a glide rule sets the equity share, mean-variance splits it.

Four sleeves, each represented by the median monthly return of its funds (Phase 4 data):

| Sleeve         | Funds (SEBI peer groups)                                  | Planning return |
|----------------|-----------------------------------------------------------|-----------------|
| large_cap      | large cap                                                 | 12.5%           |
| mid_small_cap  | mid cap, small cap                                        | 13.5%           |
| long_debt      | corporate bond, banking & PSU, gilt, dynamic bond, short  | 7.5%            |
| short_debt     | liquid, money market, ultra short, low duration           | 6.5%            |

Expected returns are PLANNING ASSUMPTIONS (an equity average of 13% and debt of ~7%, the same
as Phase 5's blend, ADR-008); historical averages over 13 years are far too noisy to optimise on.
The mid & small-cap premium is 1%: with a 0.9 correlation to large caps, a bigger premium would
always push them to their cap, whatever the investor's risk aversion (a "corner solution").
Volatilities and correlations are ESTIMATED from the data: second moments are measured much more
precisely than means, which is the usual practitioner split.

1. Glide rule: equity share = base(risk category) x clamp((years - 1) / 9, 0, 1). Full base at
   10+ years, falling linearly to no equity one year before the goal (money needed soon must
   not depend on the stock market).
2. Liquidity rule: near the goal, debt moves to short-term funds (all of it within a year, at
   least half at three years, no minimum from five years): longer bonds can fall when interest
   rates rise, and the money will be needed soon. Emergency funds stay entirely short-term.
3. Mean-variance (Markowitz): with those fixed, choose the weights that maximise
   expected return - (risk aversion / 2) x variance, long-only, mid & small cap at most half of
   the equity from 10 years out, gliding to none within 3 years (their deeper falls take years
   to recover). The risk aversion rises for more cautious investors.

Pure: no database (services/recommendations.py supplies the returns).
"""

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

SLEEVES = ("large_cap", "mid_small_cap", "long_debt", "short_debt")
EQUITY = ("large_cap", "mid_small_cap")
LABELS = {
    "large_cap": "Large-cap equity",
    "mid_small_cap": "Mid & small-cap equity",
    "long_debt": "Longer-term bonds",
    "short_debt": "Short-term debt",
}
EXPECTED_RETURN = {
    "large_cap": 0.125,
    "mid_small_cap": 0.135,
    "long_debt": 0.075,
    "short_debt": 0.065,
}

BASE_EQUITY = {"conservative": 0.30, "moderate": 0.60, "aggressive": 0.85}
DEFAULT_CATEGORY = "moderate"
FULL_GLIDE_YEARS = 10  # the base equity share applies this far from the goal and beyond
NO_EQUITY_YEARS = 1  # no equity this close to the goal
RISK_AVERSION = {"conservative": 8.0, "moderate": 4.0, "aggressive": 2.0}
MID_SMALL_MAX_OF_EQUITY = 0.5  # concentration limit, from 10 years before the goal
NO_MID_SMALL_YEARS = 3  # none this close to the goal: their deeper falls take years to recover
ALL_SHORT_YEARS = 1  # all debt in short-term funds this close to the goal
NO_SHORT_MINIMUM_YEARS = 5  # no short-term minimum this far away
MONTHS = 12


@dataclass(frozen=True)
class CapitalMarket:
    """Expected annual returns and the annual covariance matrix of the sleeves (SLEEVES order)."""

    mean: np.ndarray
    cov: np.ndarray
    months: int  # history behind the covariance

    @property
    def volatility(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov))

    def correlation(self) -> np.ndarray:
        vol = self.volatility
        return self.cov / np.outer(vol, vol)


def capital_market(monthly_returns: np.ndarray) -> CapitalMarket:
    """Covariance from aligned monthly simple returns (months x sleeves), annualised x 12."""
    if monthly_returns.shape[1] != len(SLEEVES):
        raise ValueError("one column per sleeve")
    cov = np.cov(monthly_returns, rowvar=False, ddof=1) * MONTHS
    mean = np.array([EXPECTED_RETURN[s] for s in SLEEVES])
    return CapitalMarket(mean, cov, len(monthly_returns))


def glide_equity(category: str | None, years: float) -> float:
    """Equity share for a goal `years` away: the category's base, gliding to 0 near the goal."""
    base = BASE_EQUITY.get(category or DEFAULT_CATEGORY, BASE_EQUITY[DEFAULT_CATEGORY])
    fraction = (years - NO_EQUITY_YEARS) / (FULL_GLIDE_YEARS - NO_EQUITY_YEARS)
    return base * min(max(fraction, 0.0), 1.0)


def mid_small_limit(years: float) -> float:
    """Most of the EQUITY allowed in mid & small caps: half from 10 years, none within 3."""
    fraction = (years - NO_MID_SMALL_YEARS) / (FULL_GLIDE_YEARS - NO_MID_SMALL_YEARS)
    return MID_SMALL_MAX_OF_EQUITY * min(max(fraction, 0.0), 1.0)


def short_debt_minimum(years: float) -> float:
    """Minimum share of the DEBT in short-term funds: 1 within a year, 0.5 at 3 years, 0 at 5+."""
    fraction = (NO_SHORT_MINIMUM_YEARS - years) / (NO_SHORT_MINIMUM_YEARS - ALL_SHORT_YEARS)
    return min(max(fraction, 0.0), 1.0)


def portfolio_stats(weights: np.ndarray, market: CapitalMarket) -> tuple[float, float]:
    """(expected annual return, annual volatility)."""
    return float(weights @ market.mean), float(math.sqrt(max(weights @ market.cov @ weights, 0.0)))


@dataclass(frozen=True)
class Allocation:
    weights: dict[str, float]  # sleeve -> share of the goal's money
    equity_share: float
    expected_return: float
    volatility: float
    risk_aversion: float


def optimise(
    market: CapitalMarket,
    equity_share: float,
    risk_aversion: float,
    short_minimum: float = 0.0,
    mid_small_max: float = MID_SMALL_MAX_OF_EQUITY,
) -> Allocation:
    """max  w.mu - (gamma / 2) w' S w   s.t.  sum w = 1, equity sleeves sum to e, w >= 0,
    mid & small <= mid_small_max x e, short-term debt >= short_minimum x (1 - e).
    Solved with SLSQP (sequential quadratic programming)."""
    n = len(SLEEVES)
    eq = np.array([1.0 if s in EQUITY else 0.0 for s in SLEEVES])
    mid = SLEEVES.index("mid_small_cap")
    short = SLEEVES.index("short_debt")

    def negative_utility(w: np.ndarray) -> float:
        return -(w @ market.mean - risk_aversion / 2 * (w @ market.cov @ w))

    def gradient(w: np.ndarray) -> np.ndarray:
        return -(market.mean - risk_aversion * (market.cov @ w))

    constraints = [
        {"type": "eq", "fun": lambda w: w.sum() - 1.0},
        {"type": "eq", "fun": lambda w: eq @ w - equity_share},
        {"type": "ineq", "fun": lambda w: mid_small_max * equity_share - w[mid]},
        {"type": "ineq", "fun": lambda w: w[short] - short_minimum * (1 - equity_share)},
    ]
    start = np.array(
        [
            equity_share * (1 - mid_small_max / 2),
            equity_share * mid_small_max / 2,
            (1 - equity_share) * (1 - short_minimum / 2 - 0.25),
            (1 - equity_share) * (short_minimum / 2 + 0.25),
        ]
    )
    result = minimize(
        negative_utility,
        start,
        jac=gradient,
        bounds=[(0.0, 1.0)] * n,
        constraints=constraints,
        method="SLSQP",
        options={"ftol": 1e-12, "maxiter": 200},
    )
    if not result.success:
        raise RuntimeError(f"optimisation failed: {result.message}")
    w = np.clip(result.x, 0.0, None)
    w = w / w.sum()
    expected, vol = portfolio_stats(w, market)
    return Allocation(
        weights={s: round(float(x), 4) for s, x in zip(SLEEVES, w, strict=True)},
        equity_share=round(float(eq @ w), 4),
        expected_return=expected,
        volatility=vol,
        risk_aversion=risk_aversion,
    )


def allocate(
    market: CapitalMarket, category: str | None, years: float, goal_type: str | None = None
) -> Allocation:
    category = category if category in BASE_EQUITY else DEFAULT_CATEGORY
    if goal_type == "emergency_fund":  # must be there at a day's notice
        return optimise(market, 0.0, RISK_AVERSION[category], short_minimum=1.0)
    return optimise(
        market,
        glide_equity(category, years),
        RISK_AVERSION[category],
        short_minimum=short_debt_minimum(years),
        mid_small_max=mid_small_limit(years),
    )


def efficient_frontier(market: CapitalMarket, points: int = 25) -> list[tuple[float, float]]:
    """Long-only minimum-variance portfolios for target returns from the safest to the highest
    sleeve return: (volatility, return) pairs, the Markowitz efficient frontier."""
    n = len(SLEEVES)
    low_risk = minimize(
        lambda w: w @ market.cov @ w,
        np.full(n, 1 / n),
        bounds=[(0.0, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}],
        method="SLSQP",
        options={"ftol": 1e-14},
    ).x
    lowest = float(low_risk @ market.mean)
    frontier = []
    for target in np.linspace(lowest, float(market.mean.max()), points):
        result = minimize(
            lambda w: w @ market.cov @ w,
            np.full(n, 1 / n),
            bounds=[(0.0, 1.0)] * n,
            constraints=[
                {"type": "eq", "fun": lambda w: w.sum() - 1.0},
                {"type": "eq", "fun": lambda w, t=target: w @ market.mean - t},
            ],
            method="SLSQP",
            options={"ftol": 1e-14},
        )
        if result.success:
            frontier.append(portfolio_stats(result.x, market)[::-1])
    return frontier
