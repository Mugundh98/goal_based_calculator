"""Unit tests for the Monte Carlo engine, the allocation rule and the market history helpers.

Pure code: no database. Every random test uses a fixed seed, so results are reproducible.
"""

import math
from dataclasses import replace
from datetime import date
from typing import ClassVar

import numpy as np
import pytest

from app.finance import tvm
from app.finance.goal_plan import GoalInputs, project_goal
from app.simulation import engine
from app.simulation.allocation import equity_share_for_return, return_for_equity_share
from app.simulation.history import align, annualised_volatility, portfolio_log_returns
from app.simulation.models import NormalModel

# The Phase 3 worked example: Ananya's engineering degree (98.5% funded, required SIP ₹15,254).
EXAMPLE = GoalInputs(
    target_today=2_000_000,
    years=15,
    inflation_rate=0.10,
    expected_return=0.12,
    current_savings=200_000,
    monthly_sip=15_000,
)
STEP_UP = replace(EXAMPLE, step_up_rate=0.10)
SIGMA_15 = 0.15 / math.sqrt(12)  # 15% a year


class FixedShocks:
    """A 'model' that returns given shocks, for hand-checkable cases."""

    name: ClassVar[str] = "fixed"

    def __init__(self, shocks):
        self.matrix = np.asarray(shocks, dtype=float)

    def shocks(self, rng, paths, months):
        assert self.matrix.shape == (paths, months)
        return self.matrix.copy()

    annual_volatility = 0.0

    def details(self):
        return {}


# --- Zero volatility = Phase 3 ------------------------------------------------------------------


@pytest.mark.parametrize("goal", [EXAMPLE, STEP_UP], ids=["flat SIP", "10% step-up"])
def test_zero_volatility_reproduces_the_phase_3_projection(goal):
    outcome = engine.run(goal, NormalModel(sigma=0.0), paths=50)
    projection = project_goal(goal)

    # Every path is the deterministic one, so every percentile equals the Phase 3 value (which
    # is rounded to the paisa) and the unrounded closed-form value to 12 significant digits ...
    exact = engine.deterministic_values(goal)[-1]
    for p in engine.PERCENTILES:
        assert outcome.final_percentiles[p] == pytest.approx(projection.projected_value, abs=0.005)
        assert outcome.final_percentiles[p] == pytest.approx(exact, rel=1e-12)
    assert outcome.target == pytest.approx(projection.inflated_target, abs=0.005)
    # ... year by year, too (against the closed-form tvm formulas).
    for band in outcome.bands:
        assert band.percentiles[50] == pytest.approx(band.deterministic, rel=1e-12)
    # The SIP needed is the same at any success level, and equals Phase 3's.
    assert set(outcome.required_sip.values()) == {projection.required_sip}
    # Success is all or nothing: the flat SIP is 98.5% funded (no path reaches the target), the
    # step-up plan is on track (every path does).
    if projection.on_track:
        assert outcome.success_probability == 1.0
        assert outcome.median_shortfall is None
    else:
        assert outcome.success_probability == 0.0
        assert outcome.median_shortfall == pytest.approx(projection.shortfall, abs=0.01)


def test_zero_volatility_with_the_required_sip_always_succeeds():
    goal = replace(EXAMPLE, monthly_sip=15_254)
    outcome = engine.run(goal, NormalModel(sigma=0.0), paths=10)
    assert project_goal(goal).on_track
    assert outcome.success_probability == 1.0
    assert outcome.median_shortfall is None


def test_worked_example_numbers():
    """The values quoted in the phase document (seed 2026, 10,000 paths, 15% volatility)."""
    outcome = engine.run(EXAMPLE, NormalModel(sigma=SIGMA_15))
    assert outcome.success_probability == pytest.approx(0.5011)
    assert outcome.required_sip == {50: 14977.0, 75: 20465.0, 90: 26505.0}
    assert outcome.final_percentiles[50] == pytest.approx(8_365_022.65, abs=0.01)


# --- The cash-flow arithmetic ----------------------------------------------------------------


def test_hand_calculated_two_paths():
    """₹1,00,000 for one year; path 1 grows 1% (log) every month, path 2 falls 1%."""
    goal = GoalInputs(
        target_today=100_000, years=1, inflation_rate=0, expected_return=0, current_savings=100_000
    )
    shocks = [[0.01] * 12, [-0.01] * 12]
    outcome = engine.run(goal, FixedShocks(shocks), paths=2)
    up, down = 100_000 * math.exp(0.12), 100_000 * math.exp(-0.12)  # 1,12,749.69 and 88,692.04
    assert (round(up, 2), round(down, 2)) == (112_749.69, 88_692.04)
    assert outcome.final_percentiles[10] == pytest.approx(down + 0.1 * (up - down))
    assert outcome.final_percentiles[50] == pytest.approx((up + down) / 2)
    assert outcome.success_probability == 0.5
    assert outcome.median_shortfall == pytest.approx(100_000 - down)

    # Path 2 needs SIP x B = 1,00,000 - 88,692.04, where B = value of ₹1 a month for 12 falling
    # months = sum over s of g^(12 - s), g = e^-0.01 (annuity due).
    g = math.exp(-0.01)
    b = sum(g ** (12 - s) for s in range(12))
    assert b == pytest.approx(g * (1 - g**12) / (1 - g))
    # 11,307.96 / 11.2515 = 1,005.02 -> rounded up to ₹1,006 a month
    assert outcome.required_sip[90] == math.ceil((100_000 - down) / b) == 1_006
    assert outcome.required_sip[50] == 0  # path 1 already succeeds without a SIP


def test_vectorised_engine_matches_plain_loops():
    rng = np.random.default_rng(7)
    log_returns = rng.normal(0.008, 0.05, size=(200, 60))
    growth, per_rupee = engine.year_end_components(log_returns, 0.10)
    vectorised = 50_000 * growth[:, -1] + 8_000 * per_rupee[:, -1]
    looped = engine.final_values_loop(log_returns, 50_000, 8_000, 0.10)
    np.testing.assert_allclose(vectorised, looped, rtol=1e-12)


def test_contribution_schedule_steps_up_once_a_year():
    schedule = engine.contribution_schedule(0.10, 30)
    assert list(schedule[:12]) == [1.0] * 12
    assert list(schedule[12:24]) == pytest.approx([1.1] * 12)
    assert list(schedule[24:]) == pytest.approx([1.21] * 6)


def test_bands_start_with_todays_savings_and_widen():
    outcome = engine.run(EXAMPLE, NormalModel(sigma=SIGMA_15), paths=2_000)
    assert len(outcome.bands) == 16
    assert outcome.bands[0].percentiles == dict.fromkeys(engine.PERCENTILES, 200_000)
    widths = [b.percentiles[90] - b.percentiles[10] for b in outcome.bands]
    assert widths == sorted(widths)
    for band in outcome.bands:
        values = [band.percentiles[p] for p in engine.PERCENTILES]
        assert values == sorted(values)


def test_required_sip_reaches_its_success_level():
    model = NormalModel(sigma=SIGMA_15)
    outcome = engine.run(EXAMPLE, model, paths=4_000, seed=11)
    for level, sip in outcome.required_sip.items():
        enough = engine.run(replace(EXAMPLE, monthly_sip=sip), model, paths=4_000, seed=11)
        less = engine.run(replace(EXAMPLE, monthly_sip=sip - 1), model, paths=4_000, seed=11)
        assert enough.success_probability >= level / 100
        assert less.success_probability < level / 100


def test_due_goal_cannot_be_simulated():
    with pytest.raises(tvm.FinanceInputError):
        engine.run(replace(EXAMPLE, years=0), NormalModel(sigma=0.01))


# --- Reproducibility --------------------------------------------------------------------------


def test_same_seed_same_answer_different_seed_different_answer():
    model = NormalModel(sigma=SIGMA_15)
    first = engine.run(EXAMPLE, model, paths=1_000, seed=5)
    again = engine.run(EXAMPLE, model, paths=1_000, seed=5)
    other = engine.run(EXAMPLE, model, paths=1_000, seed=6)
    assert first == again
    assert first.final_percentiles != other.final_percentiles


def test_common_random_numbers_make_a_higher_sip_never_worse():
    """With the same seed, the paths are the same, so more money can only help."""
    model = NormalModel(sigma=SIGMA_15)
    probabilities = [
        engine.run(replace(EXAMPLE, monthly_sip=sip), model, paths=2_000).success_probability
        for sip in (10_000, 15_000, 20_000, 25_000)
    ]
    assert probabilities == sorted(probabilities)
    assert probabilities[0] < probabilities[-1]


# --- Statistical sanity -----------------------------------------------------------------------


def test_median_of_a_lump_sum_is_the_deterministic_value():
    """r is the median growth rate (ADR-008): half the paths end above (1 + r)^n."""
    goal = replace(EXAMPLE, monthly_sip=0, years=10)
    outcome = engine.run(goal, NormalModel(sigma=SIGMA_15), paths=20_000)
    deterministic = 200_000 * 1.12**10
    assert outcome.final_percentiles[50] == pytest.approx(deterministic, rel=0.01)
    # The mean is higher than the median: a log-normal is skewed to the right,
    # E[V] = median x e^(sigma^2 n / 2).
    expected_mean = deterministic * math.exp(SIGMA_15**2 * 120 / 2)
    assert outcome.final_mean == pytest.approx(expected_mean, rel=0.02)


def test_a_plan_that_exactly_meets_the_target_succeeds_about_half_the_time():
    goal = GoalInputs(
        target_today=200_000 * 1.12**10,
        years=10,
        inflation_rate=0,
        expected_return=0.12,
        current_savings=200_000,
    )
    outcome = engine.run(goal, NormalModel(sigma=SIGMA_15), paths=20_000)
    # 3 standard errors of a proportion near 0.5 with 20,000 paths: 3 x sqrt(0.25 / 20,000).
    assert outcome.success_probability == pytest.approx(0.5, abs=3 * math.sqrt(0.25 / 20_000))


def test_more_volatility_means_wider_outcomes_and_less_certainty():
    goal = replace(EXAMPLE, monthly_sip=18_000)  # comfortably funded on paper
    results = [
        engine.run(goal, NormalModel(sigma=annual / math.sqrt(12)), paths=4_000)
        for annual in (0.05, 0.10, 0.20)
    ]
    spreads = [r.final_percentiles[90] - r.final_percentiles[10] for r in results]
    assert spreads == sorted(spreads)
    probabilities = [r.success_probability for r in results]
    assert probabilities == sorted(probabilities, reverse=True)


def test_estimate_error_shrinks_with_the_square_root_of_paths():
    """Law of large numbers: 16 x the paths should give about 1/4 of the spread across seeds."""
    goal = replace(EXAMPLE, years=5, monthly_sip=40_000)
    model = NormalModel(sigma=SIGMA_15)

    def spread(paths):
        estimates = [engine.run(goal, model, paths, seed).success_probability for seed in range(30)]
        return float(np.std(estimates))

    ratio = spread(250) / spread(4_000)
    assert 2.5 < ratio < 6  # theory: sqrt(16) = 4


# --- Allocation ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("annual_return", "equity_share"),
    [(0.07, 0.0), (0.08, 1 / 6), (0.10, 0.5), (0.12, 5 / 6), (0.13, 1.0), (0.15, 1.0), (0.05, 0.0)],
)
def test_equity_share_for_the_phase_3_returns(annual_return, equity_share):
    assert equity_share_for_return(annual_return) == pytest.approx(equity_share)


def test_return_for_equity_share_is_the_inverse():
    for share in (0, 0.25, 0.5, 1):
        assert equity_share_for_return(return_for_equity_share(share)) == pytest.approx(share)
    assert return_for_equity_share(0.5) == pytest.approx(0.10)
    with pytest.raises(ValueError):
        return_for_equity_share(1.2)


# --- Market history -----------------------------------------------------------------------------


def test_portfolio_return_mixes_simple_returns_then_takes_the_log():
    # Half in equity (+10%) and half in debt (+2%): +6%, i.e. ln(1.06) = 0.058269.
    result = portfolio_log_returns([0.10, -0.20], [0.02, 0.01], 0.5)
    assert result[0] == pytest.approx(math.log(1.06))
    assert result[1] == pytest.approx(math.log(0.905))
    assert annualised_volatility(np.array([0.1, -0.1, 0.1])) == pytest.approx(
        math.sqrt(1 / 75) * math.sqrt(12)
    )


def test_align_keeps_the_longest_unbroken_run_and_drops_the_latest_month():
    months = [date(2024, m, 1) for m in range(1, 13)] + [date(2025, m, 1) for m in range(1, 5)]
    equity = {m: 0.01 for m in months}
    debt = {m: 0.005 for m in months if m != date(2024, 3, 1)}  # gap in March 2024
    aligned, eq, dt = align(equity, debt, latest_month=date(2025, 4, 1))
    # April 2024 .. March 2025 (12 months, across the new year), not Jan-Feb 2024 or April 2025.
    assert aligned[0] == date(2024, 4, 1)
    assert aligned[-1] == date(2025, 3, 1)
    assert len(aligned) == len(eq) == len(dt) == 12


def test_align_with_nothing_in_common():
    assert align({date(2024, 1, 1): 0.1}, {date(2024, 2, 1): 0.1}, date(2025, 1, 1)) == (
        [],
        [],
        [],
    )
