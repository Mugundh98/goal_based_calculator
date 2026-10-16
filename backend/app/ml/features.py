"""Features and target for the fund models, built ONLY from data up to each month-end.

For every fund f and month-end t the features describe the fund's past: trailing returns, risk,
drawdown, sensitivity to the market and its standing among its peers, all computed from NAVs at
or before t. The target looks forward: the fund's return over the next 12 months, as a quartile
within its peer group at t (1 = best 25%). Nothing about the future leaks into a feature; the
tests change future NAVs and check that no feature at t moves.

Pure pandas/NumPy: no database (dataset.py loads the data).
"""

import math

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from app.ml.peers import UNRANKED

HORIZON = 12  # months ahead the target looks
MIN_PEERS = 8  # a peer group needs this many funds in a month to be ranked
RISK_FREE = 0.06  # % a year, for Sharpe (an Indian T-bill-like rate)
MONTHS = 12

# Model inputs, in a fixed order (the saved model depends on it).
FEATURES = (
    "ret_1m",
    "ret_3m",
    "ret_6m",
    "ret_12m",
    "ret_36m",
    "vol_12m",
    "vol_36m",
    "downside_36m",
    "max_dd_36m",
    "sharpe_36m",
    "beta_36m",
    "alpha_36m",
    "corr_36m",
    "age_months",
    "peer_ret_12m",
    "peer_ret_36m",
    "peer_sharpe_36m",
    "peer_vol_36m",
    "peer_alpha_36m",
    "peer_max_dd_36m",
    "peer_size",
    "market_ret_12m",
    "market_vol_12m",
    "is_equity",
    "is_debt",
    "is_hybrid",
)

# Plain-language names for explanations.
FEATURE_LABELS = {
    "ret_1m": "Return, last month",
    "ret_3m": "Return, last 3 months",
    "ret_6m": "Return, last 6 months",
    "ret_12m": "Return, last 12 months",
    "ret_36m": "Return a year, last 3 years",
    "vol_12m": "Volatility, last 12 months",
    "vol_36m": "Volatility, last 3 years",
    "downside_36m": "Downside volatility, last 3 years",
    "max_dd_36m": "Worst fall, last 3 years",
    "sharpe_36m": "Sharpe ratio, last 3 years",
    "beta_36m": "Beta to Nifty 500",
    "alpha_36m": "Alpha over Nifty 500",
    "corr_36m": "Correlation with Nifty 500",
    "age_months": "Months of history",
    "peer_ret_12m": "12-month return vs peers",
    "peer_ret_36m": "3-year return vs peers",
    "peer_sharpe_36m": "Sharpe vs peers",
    "peer_vol_36m": "Volatility vs peers",
    "peer_alpha_36m": "Alpha vs peers",
    "peer_max_dd_36m": "Worst fall vs peers",
    "peer_size": "Funds in the peer group",
    "market_ret_12m": "Market return, last 12 months",
    "market_vol_12m": "Market volatility, last 12 months",
    "is_equity": "Equity fund",
    "is_debt": "Debt fund",
    "is_hybrid": "Hybrid fund",
}

# Peer-relative features: the percentile rank among the peer group in the same month (1 = best
# for returns, Sharpe and alpha; for volatility and drawdown 1 = the riskiest / deepest fall).
PEER_RANKED = {
    "peer_ret_12m": "ret_12m",
    "peer_ret_36m": "ret_36m",
    "peer_sharpe_36m": "sharpe_36m",
    "peer_vol_36m": "vol_36m",
    "peer_alpha_36m": "alpha_36m",
    "peer_max_dd_36m": "max_dd_36m",
}


def _trailing_return(navs: pd.DataFrame, months: int) -> pd.DataFrame:
    return navs / navs.shift(months) - 1


def _max_drawdown(navs: pd.DataFrame, months: int) -> pd.DataFrame:
    """Worst peak-to-trough fall within the last `months` months (the window ends at t)."""
    values = navs.to_numpy()
    out = np.full(values.shape, np.nan)
    if len(values) > months:
        windows = sliding_window_view(values, months + 1, axis=0)  # (T - m, funds, m + 1)
        peaks = np.maximum.accumulate(windows, axis=2)
        falls = np.min(windows / peaks - 1, axis=2)  # NaN if any NAV in the window is missing
        out[months:] = falls
    return pd.DataFrame(out, index=navs.index, columns=navs.columns)


def wide_features(navs: pd.DataFrame, market: pd.Series) -> dict[str, pd.DataFrame]:
    """Per-fund features as (month x fund) frames. Rolling windows only look backwards."""
    log_returns = np.log(navs).diff()  # NaN across a gap: never one "long month"
    market_returns = np.log(market).diff()
    mean_36 = log_returns.rolling(36).mean()
    vol_36 = log_returns.rolling(36).std() * math.sqrt(MONTHS)
    market_var = market_returns.rolling(36).var()
    cov = log_returns.rolling(36).cov(market_returns)
    beta = cov.div(market_var, axis=0)
    market_mean = market_returns.rolling(36).mean()
    first_nav = navs.notna().cumsum()  # months of history so far (0 before the first NAV)

    return {
        "ret_1m": _trailing_return(navs, 1),
        "ret_3m": _trailing_return(navs, 3),
        "ret_6m": _trailing_return(navs, 6),
        "ret_12m": _trailing_return(navs, 12),
        "ret_36m": (navs / navs.shift(36)) ** (1 / 3) - 1,  # CAGR
        "vol_12m": log_returns.rolling(12).std() * math.sqrt(MONTHS),
        "vol_36m": vol_36,
        "downside_36m": np.sqrt((log_returns.clip(upper=0) ** 2).rolling(36).mean() * MONTHS),
        "max_dd_36m": _max_drawdown(navs, 36),
        "sharpe_36m": (mean_36 * MONTHS - math.log1p(RISK_FREE)) / vol_36,
        "beta_36m": beta,
        # Annualised log return not explained by the market (Jensen's alpha, without risk-free).
        "alpha_36m": (mean_36 - beta.mul(market_mean, axis=0)) * MONTHS,
        "corr_36m": log_returns.rolling(36).corr(market_returns),
        "age_months": first_nav.where(first_nav > 0),
    }


def market_features(market: pd.Series) -> pd.DataFrame:
    """The same for every fund in a month: how the market itself has been doing."""
    market_returns = np.log(market).diff()
    return pd.DataFrame(
        {
            "market_ret_12m": market / market.shift(12) - 1,
            "market_vol_12m": market_returns.rolling(12).std() * math.sqrt(MONTHS),
        }
    )


def forward_return(navs: pd.DataFrame, horizon: int = HORIZON) -> pd.DataFrame:
    """Return over the NEXT `horizon` months: the target, never a feature."""
    return navs.shift(-horizon) / navs - 1


def build_panel(
    navs: pd.DataFrame,
    market: pd.Series,
    funds: pd.DataFrame,
    horizon: int = HORIZON,
    min_peers: int = MIN_PEERS,
) -> pd.DataFrame:
    """One row per (month, fund) that can be ranked, with features and (where known) the target.

    A row needs a rankable peer group, a NAV at t and at least 12 months of history, and at
    least `min_peers` such funds in its peer group that month. `quartile` is NaN while the next
    12 months are not yet known (the rows the model scores today).
    """
    wide = wide_features(navs, market)
    wide["fwd_12m"] = forward_return(navs, horizon)
    stacked = {name: frame.stack(future_stack=True) for name, frame in wide.items()}
    panel = pd.DataFrame(stacked)
    panel.index.names = ["month", "fund_id"]
    panel = panel.reset_index().join(market_features(market), on="month")

    meta = funds[["peer_group", "asset_class"]]
    panel = panel.join(meta, on="fund_id")
    rankable = panel["peer_group"].notna() & ~panel["peer_group"].isin(UNRANKED)
    panel = panel[rankable & panel["ret_12m"].notna()].copy()

    groups = panel.groupby(["month", "peer_group"])
    panel["peer_size"] = groups["fund_id"].transform("size")
    panel = panel[panel["peer_size"] >= min_peers].copy()
    groups = panel.groupby(["month", "peer_group"])
    for feature, source in PEER_RANKED.items():
        panel[feature] = groups[source].rank(pct=True)

    for asset in ("equity", "debt", "hybrid"):
        panel[f"is_{asset}"] = (panel["asset_class"] == asset).astype(float)

    # Target: quartile of the forward return within the peer group (1 = best 25%), among the
    # funds whose forward return is known.
    known = panel["fwd_12m"].notna()
    ranks = panel[known].groupby(["month", "peer_group"])["fwd_12m"].rank(ascending=False, pct=True)
    panel["quartile"] = np.nan
    panel.loc[known, "quartile"] = np.clip(np.ceil(ranks * 4), 1, 4)
    return panel.reset_index(drop=True)


def matrix(panel: pd.DataFrame) -> np.ndarray:
    """The feature matrix in FEATURES order (NaN stays NaN: the trees route missing values)."""
    return panel[list(FEATURES)].to_numpy(dtype=float)


def snapshot(
    navs: pd.DataFrame, market: pd.Series, funds: pd.DataFrame, month: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Every fund's own features in one month (default: the latest), whatever its peer group:
    the input for clustering, which also covers index funds and unplaced categories."""
    month = navs.index[-1] if month is None else month
    wide = wide_features(navs.loc[:month], market.loc[:month])
    row = pd.DataFrame({name: frame.loc[month] for name, frame in wide.items()})
    row.index.name = "fund_id"
    row = row.join(funds[["name", "category", "asset_class", "peer_group"]])
    return row[row["ret_1m"].notna()]  # a NAV in that month
