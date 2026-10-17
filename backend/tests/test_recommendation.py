"""Unit tests for allocations, the efficient frontier and fund picks (no database)."""

import numpy as np
import pytest

from app.recommendation import allocation as A
from app.recommendation.selection import (
    Candidate,
    allocation_reasons,
    fold_small_sleeves,
    pick_funds,
)


def market(vols=(0.15, 0.19, 0.02, 0.005), corr=None) -> A.CapitalMarket:
    """A capital market close to the estimated one (Phase 8 document, section 4.2)."""
    vols = np.array(vols)
    corr = (
        np.array(
            [
                [1.0, 0.9, 0.26, 0.08],
                [0.9, 1.0, 0.2, 0.06],
                [0.26, 0.2, 1.0, 0.54],
                [0.08, 0.06, 0.54, 1.0],
            ]
        )
        if corr is None
        else corr
    )
    mean = np.array([A.EXPECTED_RETURN[s] for s in A.SLEEVES])
    return A.CapitalMarket(mean, np.outer(vols, vols) * corr, 164)


MARKET = market()


# --- Glide rules ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category, years, expected",
    [
        ("moderate", 20, 0.60),
        ("moderate", 10, 0.60),
        ("moderate", 5.5, 0.30),  # halfway between 10 and 1 years
        ("moderate", 1, 0.0),
        ("conservative", 10, 0.30),
        ("aggressive", 10, 0.85),
        (None, 10, 0.60),  # no risk profile: moderate
    ],
)
def test_glide_equity(category, years, expected):
    assert A.glide_equity(category, years) == pytest.approx(expected)


def test_liquidity_and_mid_small_rules_glide_with_the_horizon():
    assert [A.short_debt_minimum(y) for y in (0.5, 1, 3, 5, 10)] == [1, 1, 0.5, 0, 0]
    assert [A.mid_small_limit(y) for y in (2, 3, 6.5, 10, 20)] == [0, 0, 0.25, 0.5, 0.5]


# --- Optimiser -----------------------------------------------------------------------------------


def test_constraints_hold_for_every_goal():
    for category in ("conservative", "moderate", "aggressive"):
        for years in (1, 2, 3, 5, 8, 12, 25):
            a = A.allocate(MARKET, category, years)
            w = a.weights
            assert sum(w.values()) == pytest.approx(1, abs=1e-3)
            assert all(x >= 0 for x in w.values())
            assert a.equity_share == pytest.approx(A.glide_equity(category, years), abs=1e-3)
            assert w["mid_small_cap"] <= A.mid_small_limit(years) * a.equity_share + 1e-3
            debt = 1 - a.equity_share
            assert w["short_debt"] >= A.short_debt_minimum(years) * debt - 1e-3


def test_more_risk_aversion_means_fewer_mid_and_small_caps():
    shares = [
        A.optimise(MARKET, 0.6, gamma).weights["mid_small_cap"] for gamma in (1.0, 4.0, 8.0, 20.0)
    ]
    assert shares == sorted(shares, reverse=True)
    assert shares[0] > shares[-1]


def test_matches_the_closed_form_for_two_assets():
    """Equity fixed at 0, two debt assets: the utility-maximising weight has a closed form,
    w = (mu1 - mu2 + gamma (s2^2 - s12)) / (gamma (s1^2 + s2^2 - 2 s12))."""
    gamma = 30.0
    a = A.optimise(MARKET, 0.0, gamma)
    s = MARKET.cov
    mu = MARKET.mean
    long_, short = 2, 3
    expected = (mu[long_] - mu[short] + gamma * (s[short, short] - s[long_, short])) / (
        gamma * (s[long_, long_] + s[short, short] - 2 * s[long_, short])
    )
    assert a.weights["long_debt"] == pytest.approx(min(max(expected, 0), 1), abs=1e-3)


def test_due_goal_and_emergency_fund_hold_only_short_term_debt():
    for allocation in (
        A.allocate(MARKET, "aggressive", 1),
        A.allocate(MARKET, "aggressive", 20, "emergency_fund"),
    ):
        assert allocation.weights["short_debt"] == pytest.approx(1)
        assert allocation.equity_share == 0


def test_expected_return_and_volatility():
    w = np.array([0.5, 0.0, 0.5, 0.0])
    ret, vol = A.portfolio_stats(w, MARKET)
    assert ret == pytest.approx(0.5 * 0.125 + 0.5 * 0.075)
    var = 0.25 * 0.15**2 + 0.25 * 0.02**2 + 2 * 0.25 * 0.26 * 0.15 * 0.02
    assert vol == pytest.approx(var**0.5)


def test_capital_market_from_returns():
    rng = np.random.default_rng(0)
    monthly = rng.multivariate_normal(np.zeros(4), MARKET.cov / 12, size=20_000)
    estimated = A.capital_market(monthly)
    assert estimated.volatility == pytest.approx(MARKET.volatility, rel=0.03)
    assert estimated.mean.tolist() == [A.EXPECTED_RETURN[s] for s in A.SLEEVES]  # assumptions


def test_efficient_frontier_is_increasing_and_bounded():
    frontier = A.efficient_frontier(MARKET)
    vols, rets = zip(*frontier, strict=True)
    assert list(rets) == sorted(rets)
    assert all(
        b >= a - 1e-6 for a, b in zip(vols, vols[1:], strict=False)
    )  # more return, more risk
    assert rets[-1] == pytest.approx(0.135, abs=1e-4)  # all mid & small caps
    assert vols[0] <= min(MARKET.volatility) + 1e-4  # at least as safe as the safest sleeve
    # No portfolio the optimiser recommends lies above the frontier.
    a = A.allocate(MARKET, "moderate", 20)
    above = [r for v, r in frontier if v <= a.volatility + 1e-9]
    assert a.expected_return <= max(above) + 1e-4


# --- Fund picks ----------------------------------------------------------------------------------


def candidate(i, amc="A", eq=None, prob=None, sharpe=None, group="large_cap"):
    return Candidate(
        fund_id=i, name=f"Fund {i}", amc=amc, peer_group=group, expected_quartile=eq,
        prob_top=prob, predicted_quartile=1 if eq else None, peer_rank=i, peer_size=30,
        top_factor="12-month return vs peers" if eq else None, sharpe_3y=sharpe,
    )  # fmt: skip


def test_best_ranked_funds_from_different_fund_houses():
    picks = pick_funds(
        {"large_cap": 0.4, "mid_small_cap": 0.0, "long_debt": 0.0, "short_debt": 0.6},
        {
            "large_cap": [
                candidate(3, "B", eq=2.4, prob=0.30),
                candidate(1, "A", eq=2.2, prob=0.35),
                candidate(2, "A", eq=2.3, prob=0.33),  # same fund house as fund 1: skipped
            ],
            "short_debt": [candidate(7, "C", eq=2.5, prob=0.3, group="liquid")],
        },
    ).picks
    large = [p for p in picks if p.sleeve == "large_cap"]
    assert [p.fund_id for p in large] == [1, 3]
    assert all(p.weight == pytest.approx(0.2) for p in large)  # the sleeve split in two
    assert [p.fund_id for p in picks if p.sleeve == "short_debt"] == [7]  # only one available
    assert "Ranked 1 of 30 large cap funds" in large[0].reason
    assert "35% chance" in large[0].reason


def test_small_sleeves_get_one_fund_and_tiny_ones_are_folded():
    weights = {"large_cap": 0.3, "mid_small_cap": 0.01, "long_debt": 0.69, "short_debt": 0.0}
    assert fold_small_sleeves(weights) == pytest.approx(
        {"large_cap": 0.31, "mid_small_cap": 0.0, "long_debt": 0.69, "short_debt": 0.0}
    )
    picks = pick_funds(
        {"large_cap": 0.05, "mid_small_cap": 0.0, "long_debt": 0.95, "short_debt": 0.0},
        {"large_cap": [candidate(1, "A", eq=2.0, prob=0.4), candidate(2, "B", eq=2.1, prob=0.4)]},
    )
    assert [p.fund_id for p in picks.picks] == [1]  # 5% sleeve: one fund
    assert picks.notes == ["No eligible longer-term bonds fund found."]


def test_falls_back_to_sharpe_without_the_model():
    picks = pick_funds(
        {"large_cap": 1.0, "mid_small_cap": 0.0, "long_debt": 0.0, "short_debt": 0.0},
        {
            "large_cap": [
                candidate(1, "A", sharpe=0.4),
                candidate(2, "B", sharpe=0.9),
                candidate(3, "C"),
            ]
        },
    ).picks
    assert [p.fund_id for p in picks] == [2, 1]
    assert {p.basis for p in picks} == {"sharpe"}
    assert "Sharpe ratio (0.90)" in picks[0].reason


def test_reasons_explain_the_allocation():
    a = A.allocate(MARKET, "moderate", 20)
    reasons = allocation_reasons(a, MARKET, "moderate", 0.6, 20, 0.10)
    assert reasons[0].startswith("Your moderate risk profile allows 60% in equity")
    assert "the glide rule sets 60%" in reasons[0]
    assert "The goal currently assumes 10.0%." in reasons[-1]
    due = allocation_reasons(A.allocate(MARKET, "moderate", 1), MARKET, "moderate", 0.6, 1, None)
    assert due[0].startswith("The goal is 1 year away")
