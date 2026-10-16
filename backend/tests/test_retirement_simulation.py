"""Unit tests for the lifetime (retirement) Monte Carlo. Pure code, fixed seeds."""

import math
from dataclasses import replace

import numpy as np
import pytest

from app.finance.retirement import plan_retirement
from app.simulation import retirement as sim
from app.simulation.models import NormalModel
from tests.test_retirement_plan import EXAMPLE
from tests.test_simulation_engine import FixedShocks

ZERO = NormalModel(sigma=0.0)
PRE = NormalModel(sigma=0.12 / math.sqrt(12))  # 12% a year before retirement
POST = NormalModel(sigma=0.05 / math.sqrt(12))  # 5% a year after (a debt-heavy mix)
REQUIRED = plan_retirement(EXAMPLE).accumulation.required_sip  # ₹26,481


def lifetime_loop(plan, pre_shocks, post_shocks):
    """Independent reference with plain loops: year-end balances and the month the money ran out."""
    i_pre = math.log1p(plan.pre_retirement_return) / 12
    i_post = math.log1p(plan.post_retirement_return) / 12
    value, balances = plan.current_savings, []
    for month, shock in enumerate(pre_shocks):
        value = (value + plan.monthly_sip * (1 + plan.step_up_rate) ** (month // 12)) * math.exp(
            i_pre + shock
        )
        if month % 12 == 11:
            balances.append(value)
    first = plan.monthly_expense * (1 + plan.inflation_rate) ** plan.years_to_retirement
    ran_out = None
    for month, shock in enumerate(post_shocks):
        value -= first * (1 + plan.inflation_rate) ** (month // 12)
        if value < -0.5 and ran_out is None:
            ran_out = month
        value = max(value, 0.0) * math.exp(i_post + shock)
        if month % 12 == 11:
            balances.append(value)
    return balances, ran_out


# --- Zero volatility = the single-return plan ------------------------------------------------


def test_zero_volatility_reproduces_the_plan():
    outcome = sim.run(EXAMPLE, ZERO, ZERO, paths=20)
    plan = plan_retirement(EXAMPLE)
    for band in outcome.bands:
        for value in band.percentiles.values():
            assert value == pytest.approx(band.deterministic, abs=0.01)
    assert [b.age for b in outcome.bands] == list(range(34, 86))
    assert outcome.success_probability == 0  # the plan runs out at 70 on every path
    assert outcome.depletion_age_p10 == pytest.approx(plan.money_lasts_until, abs=0.05)
    assert outcome.median_depletion_age == pytest.approx(70.17, abs=0.01)
    for level in sim.SUCCESS_LEVELS:
        assert outcome.required_sip[level] == REQUIRED
        assert outcome.corpus_needed[level] == math.ceil(plan.corpus_needed)


def test_zero_volatility_with_the_required_sip_always_lasts():
    outcome = sim.run(replace(EXAMPLE, monthly_sip=REQUIRED), ZERO, ZERO, paths=10)
    assert outcome.success_probability == 1
    assert all(share == 1 for _, share in outcome.survival)
    assert outcome.median_depletion_age is None
    assert outcome.depletion_age_p10 == 85  # "never" = life expectancy


# --- Vectorised = plain loops -------------------------------------------------------------------


@pytest.mark.parametrize("step_up", [0.0, 0.10])
def test_vectorised_simulation_matches_a_plain_loop(step_up):
    plan = replace(EXAMPLE, step_up_rate=step_up)
    rng = np.random.default_rng(7)
    pre = rng.normal(0, 0.05, (1, plan.years_to_retirement * 12))
    post = rng.normal(0, 0.05, (1, plan.retirement_years * 12))
    outcome = sim.run(plan, FixedShocks(pre), FixedShocks(post), paths=1)
    balances, ran_out = lifetime_loop(plan, pre[0], post[0])
    for band, expected in zip(outcome.bands[1:], balances, strict=True):
        assert band.percentiles[50] == pytest.approx(expected, rel=1e-9, abs=1e-6)
    expected_age = 85 if ran_out is None else 60 + ran_out / 12
    assert outcome.depletion_age_p10 == pytest.approx(expected_age)
    assert outcome.success_probability == (1.0 if ran_out is None else 0.0)


# --- Results with volatility ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def outcome():
    return sim.run(replace(EXAMPLE, monthly_sip=REQUIRED), PRE, POST, paths=4_000, seed=11)


def test_the_single_return_plan_succeeds_about_half_the_time(outcome):
    """ADR-008: the expected return is the median, so an exactly funded plan is a coin flip."""
    assert 0.42 <= outcome.success_probability <= 0.58


def test_survival_falls_with_age_and_ends_at_the_success_probability(outcome):
    shares = [share for _, share in outcome.survival]
    assert shares[0] == 1
    assert all(a >= b for a, b in zip(shares, shares[1:], strict=False))
    assert shares[-1] == pytest.approx(outcome.success_probability)
    assert [age for age, _ in outcome.survival] == list(range(60, 86))


def test_more_certainty_costs_more(outcome):
    sips = [outcome.required_sip[level] for level in sim.SUCCESS_LEVELS]
    corpora = [outcome.corpus_needed[level] for level in sim.SUCCESS_LEVELS]
    assert sips == sorted(sips) and len(set(sips)) == 3
    assert corpora == sorted(corpora) and len(set(corpora)) == 3
    # The median corpus needed is close to the single-return corpus (₹4.25 Cr).
    assert outcome.corpus_needed[50] == pytest.approx(outcome.corpus_target, rel=0.03)


@pytest.mark.parametrize("level", sim.SUCCESS_LEVELS)
def test_required_sip_reaches_its_success_level(level):
    """Same seed = same paths: the SIP for q% succeeds on q% of them, one rupee less does not."""
    base = sim.run(EXAMPLE, PRE, POST, paths=2_000, seed=5)
    sip = base.required_sip[level]
    hit = sim.run(replace(EXAMPLE, monthly_sip=sip), PRE, POST, paths=2_000, seed=5)
    miss = sim.run(replace(EXAMPLE, monthly_sip=sip - 1), PRE, POST, paths=2_000, seed=5)
    assert hit.success_probability >= level / 100
    assert miss.success_probability < level / 100


def test_a_higher_sip_is_never_worse():
    chances = [
        sim.run(
            replace(EXAMPLE, monthly_sip=sip), PRE, POST, paths=1_000, seed=3
        ).success_probability
        for sip in (10_000, 20_000, 30_000, 40_000)
    ]
    assert chances == sorted(chances)


def test_runs_are_reproducible():
    a = sim.run(EXAMPLE, PRE, POST, paths=500, seed=9)
    b = sim.run(EXAMPLE, PRE, POST, paths=500, seed=9)
    assert a == b


def test_failed_paths_run_out_after_retirement(outcome):
    assert 60 <= outcome.depletion_age_p10 <= 85
    assert outcome.median_depletion_age is not None
    assert 60 < outcome.median_depletion_age < 85
