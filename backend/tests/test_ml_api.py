"""API, registry and scoring tests for the ML models (real test database, synthetic data)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.ml import clustering, features, ranking, registry, scoring
from app.ml.dataset import MonthlyData
from app.models import Fund, FundCluster, FundPrediction, MLModel
from tests.test_ml_models import blobs

MONTHS = pd.date_range("2018-01-01", periods=60, freq="MS")
LAST = MONTHS[-1].date()


def make_funds(db, count=16):
    funds = [
        Fund(
            scheme_code=900_000 + i,
            name=f"Test {'Large' if i < 8 else 'Mid'} Cap Fund {i} - Direct Plan - Growth",
            amc="Test AMC",
            scheme_type="Open Ended",
            category="Large Cap Fund" if i < 8 else "Mid Cap Fund",
            asset_class="equity",
            plan="direct",
            option="growth",
        )
        for i in range(count)
    ]
    db.add_all(funds)
    db.flush()
    return funds


def monthly_data(funds) -> MonthlyData:
    rng = np.random.default_rng(0)
    navs = pd.DataFrame(
        {f.id: 100 * np.exp(np.cumsum(rng.normal(0.01, 0.05, len(MONTHS)))) for f in funds},
        index=MONTHS,
    )
    market = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.01, 0.04, len(MONTHS)))), index=MONTHS)
    meta = pd.DataFrame(
        {
            "name": [f.name for f in funds],
            "amc": [f.amc for f in funds],
            "category": [f.category for f in funds],
            "asset_class": "equity",
            "peer_group": [
                "large_cap" if f.category.startswith("Large") else "mid_cap" for f in funds
            ],
        },
        index=pd.Index([f.id for f in funds], name="fund_id"),
    )
    return MonthlyData(navs=navs, market=market, funds=meta)


@pytest.fixture
def trained(db, tmp_path, monkeypatch):
    """Funds, a small ranker saved to a temporary folder, and a cluster model, all active."""
    monkeypatch.setattr(registry, "MODELS_DIR", tmp_path)
    funds = make_funds(db)
    data = monthly_data(funds)
    panel = features.build_panel(data.navs, data.market, data.funds)
    labelled = panel[panel["quartile"].notna()]
    model = ranking.train(labelled, rounds=20)
    path = registry.model_path("fund_ranker", 1)
    model.save_model(str(path))
    registry.register(
        db,
        name="fund_ranker",
        version=1,
        algorithm="LightGBM",
        params={},
        metrics={
            "reported_years": {"pooled": {"model": {"rank_ic": 0.1}}},
            "leaky_random_split": {"rank_ic": 0.4},
            "importance": [{"feature": "ret_12m", "mean_abs_shap": 0.1}],
            "rows": len(labelled),
            "funds": 16,
        },
        features=list(features.FEATURES),
        file_path=path,
        data_start=date(2019, 1, 1),
        data_end=LAST,
    )
    cluster_model, report = clustering.fit(blobs())
    registry.register(
        db,
        name="fund_clusters",
        version=1,
        algorithm="K-Means",
        params={"model": cluster_model.to_json()},
        metrics=report,
        data_start=date(2020, 1, 1),
        data_end=LAST,
    )
    return funds, data


# --- Not trained yet ---------------------------------------------------------------------------


def test_endpoints_require_login(client):
    for url in ("/api/ml/models", "/api/ml/rankings", "/api/ml/clusters", "/api/ml/inflation"):
        assert client.get(url).status_code == 401


def test_untrained_models_answer_409(client, auth_headers):
    assert client.get("/api/ml/models", headers=auth_headers).json() == []
    for url in ("/api/ml/rankings", "/api/ml/clusters", "/api/ml/inflation"):
        response = client.get(url, headers=auth_headers)
        assert response.status_code == 409
        assert "python -m app.ml train" in response.json()["detail"]


# --- Registry ---------------------------------------------------------------------------------


def test_registering_a_new_version_deactivates_the_old_one(db):
    kwargs = dict(
        name="inflation_forecast",
        algorithm="SARIMA",
        params={},
        metrics={},
        data_start=date(2011, 1, 1),
        data_end=date(2025, 12, 1),
    )
    first = registry.register(db, version=1, **kwargs)
    second = registry.register(
        db, version=registry.next_version(db, "inflation_forecast"), **kwargs
    )
    db.refresh(first)
    assert second.version == 2
    assert (first.is_active, second.is_active) == (False, True)
    assert registry.active(db, "inflation_forecast").id == second.id


def test_database_allows_only_one_active_version(db):
    for version in (1, 2):
        db.add(
            MLModel(
                name="fund_ranker",
                version=version,
                algorithm="x",
                params={},
                metrics={},
                data_start=date(2020, 1, 1),
                data_end=date(2020, 1, 1),
                is_active=True,
            )
        )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# --- Scoring and reading -----------------------------------------------------------------------


def test_scoring_writes_predictions_with_explanations(db, trained):
    funds, data = trained
    assert scoring.score_rankings(db, data) == 16
    rows = db.scalars(select(FundPrediction)).all()
    assert {r.as_of for r in rows} == {LAST}
    for group in ("large_cap", "mid_cap"):
        ranks = sorted(r.peer_rank for r in rows if r.peer_group == group)
        assert ranks == list(range(1, 9))
    row = rows[0]
    assert sum(row.probabilities) == pytest.approx(1, abs=1e-3)
    assert len(row.factors) == scoring.TOP_FACTORS
    assert {"feature", "label", "value", "contribution"} <= set(row.factors[0])
    # Scoring again replaces the rows instead of adding to them.
    scoring.score_rankings(db, data)
    assert db.scalar(select(func.count()).select_from(FundPrediction)) == 16


def test_rankings_endpoint(client, auth_headers, db, trained):
    scoring.score_rankings(db, trained[1])
    body = client.get("/api/ml/rankings", headers=auth_headers).json()
    assert {g["id"] for g in body["peer_groups"]} == {"large_cap", "mid_cap"}
    assert body["peer_group"] in {"large_cap", "mid_cap"}
    assert [f["peer_rank"] for f in body["funds"]] == list(range(1, 9))
    scores = [f["expected_quartile"] for f in body["funds"]]
    assert scores == sorted(scores)  # best first
    mid = client.get("/api/ml/rankings?peer_group=mid_cap", headers=auth_headers).json()
    assert all(f["category"] == "Mid Cap Fund" for f in mid["funds"])
    assert body["as_of"] == LAST.isoformat()


def test_clusters_endpoint_and_fund_insight(client, auth_headers, db, trained):
    funds, data = trained
    scoring.score_rankings(db, data)
    assert scoring.assign_clusters(db, data) == 16  # every fund has 3 years of history
    body = client.get("/api/ml/clusters", headers=auth_headers).json()
    assert body["k"] == 5
    assert len(body["points"]) == 16
    assert len(body["clusters"]) == 5
    insight = client.get(f"/api/ml/funds/{funds[0].id}", headers=auth_headers).json()
    assert insight["prediction"]["fund_id"] == funds[0].id
    assert insight["peer_group_label"] == "Large cap"
    assert insight["cluster_name"] is not None
    assert db.scalar(select(func.count()).select_from(FundCluster)) == 16


def test_fund_without_models_has_an_empty_insight(client, auth_headers, db):
    fund = make_funds(db, 1)[0]
    insight = client.get(f"/api/ml/funds/{fund.id}", headers=auth_headers).json()
    assert insight["prediction"] is None and insight["cluster"] is None
    assert client.get("/api/ml/funds/999999", headers=auth_headers).status_code == 404


def test_model_cards(client, auth_headers, trained):
    cards = {c["name"]: c for c in client.get("/api/ml/models", headers=auth_headers).json()}
    assert set(cards) == {"fund_ranker", "fund_clusters"}
    assert cards["fund_ranker"]["summary"]["leaky_random_split"]["rank_ic"] == 0.4
    assert cards["fund_clusters"]["summary"]["k"] == 5


def test_inflation_endpoint(client, auth_headers, db):
    registry.register(
        db,
        name="inflation_forecast",
        version=1,
        algorithm="SARIMA(0, 1, 1)x(0, 1, 1, 12)",
        params={},
        metrics={
            "order": [0, 1, 1],
            "seasonal_order": [0, 1, 1, 12],
            "evaluation": {"mae_12m_ahead": {"sarima": 1.3, "naive": 1.7, "rbi_target": 1.9}},
            "forecast": [{"month": "2026-01-01", "p10": 1.5, "p50": 2.2, "p90": 2.9}],
            "history": [{"month": f"2025-{m:02d}-01", "yoy": 2.0} for m in range(1, 13)],
        },
        data_start=date(2011, 1, 1),
        data_end=date(2025, 12, 1),
    )
    body = client.get("/api/ml/inflation", headers=auth_headers).json()
    assert body["forecast"][0]["p50"] == 2.2
    assert len(body["history"]) == 12
    assert body["mae_12m_ahead"]["sarima"] == 1.3
