"""Unit tests for the fund features and target (no database)."""

import math

import numpy as np
import pandas as pd
import pytest

from app.ml import features as F
from app.ml.peers import peer_group

MONTHS = pd.date_range("2015-01-01", periods=72, freq="MS")


def growing(rate_per_month: float, start: float = 100.0) -> np.ndarray:
    return start * (1 + rate_per_month) ** np.arange(len(MONTHS))


def frame(columns: dict[int, np.ndarray]) -> pd.DataFrame:
    return pd.DataFrame(columns, index=MONTHS)


def funds_meta(ids, group="large_cap", asset="equity") -> pd.DataFrame:
    return pd.DataFrame(
        {"peer_group": group, "asset_class": asset, "name": "x", "category": "y"},
        index=pd.Index(ids, name="fund_id"),
    )


MARKET = pd.Series(growing(0.01), index=MONTHS)


# --- Peer groups ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category, expected",
    [
        ("Large Cap Fund", "large_cap"),
        ("Large & Mid Cap Fund", "large_mid_cap"),  # not "large cap"
        ("ELSS- Tax Saver Fund", "elss"),
        ("Short Term Fund", "short_duration"),
        ("Short Duration Fund", "short_duration"),
        ("Ultra Short to Short Term Fund", "low_duration"),  # not "ultra short"
        ("Banking and PSU Debt Fund", "banking_psu"),
        ("Index Funds", "index"),
        ("Equity Funds", None),  # pre-2017 generic label: cannot be placed
    ],
)
def test_peer_groups(category, expected):
    assert peer_group(category) == expected


# --- Features ------------------------------------------------------------------------------------


def test_trailing_returns_and_cagr():
    navs = frame({1: growing(0.01)})
    wide = F.wide_features(navs, MARKET)
    t = MONTHS[-1]
    assert wide["ret_1m"].loc[t, 1] == pytest.approx(0.01)
    assert wide["ret_12m"].loc[t, 1] == pytest.approx(1.01**12 - 1)
    assert wide["ret_36m"].loc[t, 1] == pytest.approx(1.01**12 - 1)  # CAGR = the yearly rate
    assert math.isnan(wide["ret_36m"].iloc[35, 0])  # not enough history yet


def test_steady_growth_has_no_volatility_or_drawdown():
    wide = F.wide_features(frame({1: growing(0.01)}), MARKET)
    assert wide["vol_36m"].iloc[-1, 0] == pytest.approx(0, abs=1e-12)
    assert wide["max_dd_36m"].iloc[-1, 0] == pytest.approx(0)


def test_max_drawdown_finds_the_worst_fall():
    nav = np.full(len(MONTHS), 100.0)
    nav[50:] = 70.0  # a 30% fall that never recovers
    nav[60:] = 90.0
    wide = F.wide_features(frame({1: nav}), MARKET)
    assert wide["max_dd_36m"].iloc[-1, 0] == pytest.approx(-0.30)
    assert wide["max_dd_36m"].iloc[45, 0] == pytest.approx(0)  # before the fall


def test_a_fund_that_is_the_market_has_beta_one_and_no_alpha():
    rng = np.random.default_rng(1)
    market = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.01, 0.05, len(MONTHS)))), index=MONTHS)
    wide = F.wide_features(frame({1: market.to_numpy()}), market)
    assert wide["beta_36m"].iloc[-1, 0] == pytest.approx(1)
    assert wide["alpha_36m"].iloc[-1, 0] == pytest.approx(0, abs=1e-12)
    assert wide["corr_36m"].iloc[-1, 0] == pytest.approx(1)


def test_features_never_look_ahead():
    """Changing the NAVs after month t must not change a single feature at or before t."""
    rng = np.random.default_rng(2)
    navs = frame(
        {i: 100 * np.exp(np.cumsum(rng.normal(0.01, 0.04, len(MONTHS)))) for i in range(8)}
    )
    meta = funds_meta(range(8))
    before = F.build_panel(navs, MARKET, meta)
    cut = MONTHS[40]
    changed = navs.copy()
    changed.loc[changed.index > cut] *= 3.0  # rewrite the future
    after = F.build_panel(changed, MARKET, meta)
    columns = list(F.FEATURES)
    past_before = before[before["month"] <= cut].set_index(["month", "fund_id"])[columns]
    past_after = after[after["month"] <= cut].set_index(["month", "fund_id"])[columns]
    pd.testing.assert_frame_equal(past_before, past_after)


# --- Target --------------------------------------------------------------------------------------


def test_forward_return_is_the_next_twelve_months():
    fwd = F.forward_return(frame({1: growing(0.01)}))
    assert fwd.iloc[0, 0] == pytest.approx(1.01**12 - 1)
    assert fwd.iloc[-12:, 0].isna().all()  # not known yet


def test_quartiles_within_the_peer_group():
    # Eight funds growing at different steady rates: the fastest two are quartile 1, etc.
    navs = frame({i: growing(0.002 * (i + 1)) for i in range(8)})
    panel = F.build_panel(navs, MARKET, funds_meta(range(8)))
    month = panel[panel["month"] == MONTHS[20]].set_index("fund_id")
    assert month["quartile"].to_dict() == {7: 1, 6: 1, 5: 2, 4: 2, 3: 3, 2: 3, 1: 4, 0: 4}
    assert month.loc[7, "peer_ret_12m"] == 1.0  # best trailing return in the group
    assert month["peer_size"].eq(8).all()
    assert panel[panel["month"] == MONTHS[-1]]["quartile"].isna().all()  # future unknown


def test_small_or_unranked_peer_groups_are_left_out():
    navs = frame({i: growing(0.01) for i in range(12)})
    meta = pd.concat(
        [
            funds_meta(range(0, 7), "mid_cap"),  # only 7 funds: below MIN_PEERS
            funds_meta(range(7, 12), "index", "index"),  # index funds are not ranked
        ]
    )
    assert F.build_panel(navs, MARKET, meta).empty
