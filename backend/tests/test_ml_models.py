"""Unit tests for the ranker, the clusters and the inflation forecast (synthetic data)."""

import numpy as np
import pandas as pd
import pytest

from app.ml import clustering, inflation, ranking
from app.ml.features import FEATURES

# --- Synthetic ranking panel ---------------------------------------------------------------------


def synthetic_panel(months: int = 72, funds: int = 40, signal: float = 1.0, seed: int = 0):
    """Peer groups of 20 funds; next year's return depends on peer_alpha_36m plus noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for month in pd.date_range("2016-01-01", periods=months, freq="MS"):
        for f in range(funds):
            row = {name: rng.normal() for name in FEATURES}
            row |= {"month": month, "fund_id": f, "peer_group": f"g{f % 2}"}
            row["fwd_12m"] = signal * row["peer_alpha_36m"] + rng.normal()
            rows.append(row)
    panel = pd.DataFrame(rows)
    ranks = panel.groupby(["month", "peer_group"])["fwd_12m"].rank(ascending=False, pct=True)
    panel["quartile"] = np.clip(np.ceil(ranks * 4), 1, 4)
    return panel


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel()


@pytest.fixture(scope="module")
def model(panel):
    return ranking.train(panel, rounds=60)


def test_walk_forward_folds_purge_the_target_window():
    months = pd.Series(pd.date_range("2014-01-01", "2025-12-01", freq="MS"))
    folds = ranking.walk_forward_folds(months, [2020, 2021])
    assert [f.year for f in folds] == [2020, 2021]
    for fold in folds:
        start = pd.Timestamp(year=fold.year, month=1, day=1)
        latest_train = months[fold.train].max()
        # The newest training month's 12-month target ends no later than the test year starts.
        assert latest_train + pd.DateOffset(months=12) <= start
        assert set(months[fold.test].dt.year) == {fold.year}
        assert not (fold.train & fold.test).any()


def test_model_learns_a_real_signal(panel, model):
    test = synthetic_panel(months=12, seed=1)
    probs = ranking.probabilities(model, test)
    metrics = ranking.evaluate(test, probs, -ranking.expected_quartile(probs))
    assert probs.shape == (len(test), 4)
    assert np.allclose(probs.sum(axis=1), 1)
    assert metrics["rank_ic"] > 0.3
    assert metrics["accuracy"] > 0.30  # random: 0.25
    assert metrics["top_pick_hit_rate"] > 0.35


def test_no_signal_means_no_skill():
    noise = synthetic_panel(signal=0.0, seed=2)
    model = ranking.train(noise, rounds=60)
    test = synthetic_panel(months=12, signal=0.0, seed=3)
    probs = ranking.probabilities(model, test)
    assert abs(ranking.evaluate(test, probs, -ranking.expected_quartile(probs))["rank_ic"]) < 0.1


def test_shap_values_add_up_to_the_model_output(panel, model):
    """Tree SHAP is exact: base value + contributions = the raw score for 'top quartile'."""
    rows = panel.head(50)
    contributions = ranking.contributions(model, rows)
    raw = model.predict(rows[list(FEATURES)].to_numpy(float), raw_score=True)[:, ranking.TOP]
    assert contributions.shape == (50, len(FEATURES) + 1)
    assert np.allclose(contributions.sum(axis=1), raw, atol=1e-6)


def test_the_signal_feature_matters_most(panel, model):
    assert ranking.global_importance(model, panel)[0]["feature"] == "peer_alpha_36m"


def test_perfect_scores_give_perfect_ranking_metrics(panel):
    frame = panel.head(400)
    metrics = ranking.evaluate(frame, None, frame["fwd_12m"].to_numpy())
    assert metrics["rank_ic"] == pytest.approx(1)
    assert metrics["top_pick_hit_rate"] == pytest.approx(1)


def test_expected_quartile():
    probs = np.array([[1, 0, 0, 0], [0.25, 0.25, 0.25, 0.25], [0, 0, 0, 1]])
    assert ranking.expected_quartile(probs).tolist() == [1, 2.5, 4]


def test_validation_compares_model_baselines_and_the_leaky_split():
    # Enough rows for the real setting of at least 1,000 fund-months per leaf.
    data = synthetic_panel(months=96, funds=60, seed=4)
    report = ranking.validate(data, [2021, 2022], rounds=40)
    assert [f["year"] for f in report.folds] == [2021, 2022]
    assert set(report.pooled) == {"model", "momentum", "random"}
    assert report.pooled["model"]["rank_ic"] > report.pooled["random"]["rank_ic"]
    assert "accuracy" in report.leaky


# --- Clusters ------------------------------------------------------------------------------------


def blobs(seed: int = 0) -> pd.DataFrame:
    """Five well-separated groups of funds in the cluster feature space."""
    rng = np.random.default_rng(seed)
    centres = [
        (0.07, 0.003, 0.002, 0.0, 3.0, 0.0, 0.3),  # cash-like
        (0.07, 0.02, 0.01, -0.01, 0.5, 0.05, 0.4),  # bonds
        (0.09, 0.08, 0.05, -0.08, 0.4, 0.4, 0.95),  # hybrid
        (0.13, 0.15, 0.10, -0.18, 0.5, 0.95, 0.96),  # equity
        (0.20, 0.17, 0.11, -0.12, 0.9, 0.5, 0.65),  # gold-like
    ]
    rows = []
    for i, centre in enumerate(centres):
        for _ in range(30):
            values = np.array(centre) * (1 + rng.normal(0, 0.03, len(centre)))
            rows.append(
                dict(zip(clustering.CLUSTER_FEATURES, values, strict=True))
                | {
                    "asset_class": ["debt", "debt", "hybrid", "equity", "index"][i],
                    "peer_group": f"g{i}",
                    "truth": i,
                }
            )
    return pd.DataFrame(rows)


def test_clusters_recover_separated_groups():
    data = blobs()
    model, report = clustering.fit(data)
    assert report["k"] == 5
    labels, distances = model.assign(data[list(clustering.CLUSTER_FEATURES)].to_numpy(float))
    from sklearn.metrics import adjusted_rand_score

    assert adjusted_rand_score(data["truth"], labels) == pytest.approx(1)
    assert (distances >= 0).all()
    # Ordered from least to most volatile: cluster 0 is the cash-like group.
    assert set(labels[data["truth"] == 0]) == {0}
    assert len(set(model.names)) == 5  # unique names
    assert model.names[0].startswith("Cash-like")


def test_cluster_model_survives_json():
    model, _ = clustering.fit(blobs())
    copy = clustering.ClusterModel.from_json(model.to_json())
    values = blobs(seed=1)[list(clustering.CLUSTER_FEATURES)].to_numpy(float)
    assert (copy.assign(values)[0] == model.assign(values)[0]).all()


def test_cluster_names_describe_risk_and_market_link():
    centroids = pd.DataFrame(
        [
            {"vol_36m": 0.005, "sharpe_36m": 2.0, "corr_36m": 0.3, "beta_36m": 0.0},
            {"vol_36m": 0.15, "sharpe_36m": 0.3, "corr_36m": 0.95, "beta_36m": 1.1},
            {"vol_36m": 0.16, "sharpe_36m": 0.9, "corr_36m": 0.6, "beta_36m": 0.5},
        ]
    )
    names = clustering.name_clusters(centroids)
    assert names[0] == "Cash-like, strong risk-adjusted return"
    assert names[1] == "High risk, amplifies the market, weaker risk-adjusted return"
    assert names[2] == "High risk, moves apart from the market, strong risk-adjusted return"


# --- Inflation -----------------------------------------------------------------------------------


def synthetic_cpi(months: int = 120, seed: int = 0) -> pd.Series:
    """CPI with ~5% a year trend inflation and a yearly seasonal pattern."""
    rng = np.random.default_rng(seed)
    t = np.arange(months)
    log_cpi = np.log(100) + t * np.log(1.05) / 12 + 0.01 * np.sin(2 * np.pi * t / 12)
    log_cpi += np.cumsum(rng.normal(0, 0.002, months))
    return pd.Series(np.exp(log_cpi), index=pd.date_range("2012-01-01", periods=months, freq="MS"))


def test_year_on_year_inflation():
    cpi = pd.Series(
        [100.0] * 12 + [106.0], index=pd.date_range("2020-01-01", periods=13, freq="MS")
    )
    assert inflation.yoy(cpi).iloc[-1] == pytest.approx(0.06)


def test_forecast_band_is_ordered_and_near_the_trend():
    cpi = synthetic_cpi()
    band = inflation.forecast_band(cpi, (0, 1, 1), (0, 1, 1, 12))
    assert len(band) == 12
    assert all(b["p10"] < b["p50"] < b["p90"] for b in band)
    assert all(3 < b["p50"] < 7 for b in band)  # around the 5% trend
    assert band[-1]["p90"] - band[-1]["p10"] > band[0]["p90"] - band[0]["p10"]  # widens


def test_order_selection_and_walk_forward_evaluation():
    cpi = synthetic_cpi()
    order, seasonal, grid = inflation.choose_order(np.log(cpi.iloc[:72]))
    assert grid[0]["aic"] <= grid[-1]["aic"]
    origins = list(pd.date_range("2018-01-01", "2019-12-01", freq="6MS"))
    result = inflation.evaluate(cpi, order, seasonal, origins)
    assert result.origins == ["2018-01", "2018-07", "2019-01", "2019-07"]
    assert set(result.mae) == {"sarima", "naive", "rbi_target"}
    assert len(result.mae_by_horizon["sarima"]) == 12
