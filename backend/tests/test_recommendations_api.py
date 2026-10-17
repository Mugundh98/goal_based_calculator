"""API tests for recommendations (real test database, synthetic market data)."""

from datetime import UTC, date, datetime
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import func, select

from app.ml import registry
from app.models import Fund, FundMetrics, FundPrediction, Goal, NavHistory, Recommendation
from app.services import recommendations as service
from tests.conftest import login_headers

THIS_YEAR = date.today().year
MONTHS = 72
# (category, yearly drift, monthly volatility) per synthetic sleeve fund group
GROUPS = {
    "Large Cap Fund": (0.12, 0.045),
    "Mid Cap Fund": (0.14, 0.055),
    "Corporate Bond Fund": (0.075, 0.006),
    "Liquid Fund": (0.065, 0.001),
}


def month_end(i: int) -> date:
    year, month = divmod(2020 * 12 + i, 12)
    return date(year, month + 1, 28)


@pytest.fixture
def market(db):
    """Three direct-growth funds per sleeve with six years of month-end NAVs and metrics."""
    service._cache.clear()  # earlier tests' data was rolled back
    rng = np.random.default_rng(0)
    funds: dict[str, list[Fund]] = {}
    code = 950_000
    for category, (drift, vol) in GROUPS.items():
        funds[category] = []
        for k in range(3):
            code += 1
            fund = Fund(
                scheme_code=code,
                name=f"{category.replace(' Fund', '')} Fund {k} - Direct Plan - Growth",
                amc=f"AMC {k}",
                scheme_type="Open Ended",
                category=category,
                asset_class="debt" if "Bond" in category or "Liquid" in category else "equity",
                plan="direct",
                option="growth",
                latest_nav_date=month_end(MONTHS - 1),
            )
            db.add(fund)
            db.flush()
            nav = 100.0
            for i in range(MONTHS):
                nav *= 1 + drift / 12 + rng.normal(0, vol)
                db.add(
                    NavHistory(fund_id=fund.id, nav_date=month_end(i), nav=Decimal(f"{nav:.4f}"))
                )
            db.add(
                FundMetrics(
                    fund_id=fund.id, as_of_date=month_end(MONTHS - 1), history_start=month_end(0),
                    return_3y=10.0, sharpe=0.5 + 0.1 * k, risk_free_rate=6.0,
                    computed_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )  # fmt: skip
            funds[category].append(fund)
    db.commit()
    return funds


def goal(client, headers, **overrides):
    body = {"goal_type": "education", "name": "College", "target_amount": 2000000,
            "target_year": THIS_YEAR + 15} | overrides  # fmt: skip
    response = client.post("/api/goals", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def recommend(client, headers, goal_id):
    response = client.post(f"/api/goals/{goal_id}/recommendations", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Access and preconditions ------------------------------------------------------------------


def test_requires_login_and_own_goal(client, auth_headers):
    goal_id = goal(client, auth_headers)
    assert client.post(f"/api/goals/{goal_id}/recommendations").status_code == 401
    other = login_headers(client, "other@example.com")
    assert client.post(f"/api/goals/{goal_id}/recommendations", headers=other).status_code == 404
    assert client.get(f"/api/goals/{goal_id}/recommendations", headers=other).status_code == 404


def test_needs_market_data(client, auth_headers):
    service._cache.clear()
    goal_id = goal(client, auth_headers)
    response = client.post(f"/api/goals/{goal_id}/recommendations", headers=auth_headers)
    assert response.status_code == 409
    assert "market data pipeline" in response.json()["detail"]


# --- Recommending -----------------------------------------------------------------------------


def test_recommendation_for_a_long_goal(client, auth_headers, market):
    r = recommend(client, auth_headers, goal(client, auth_headers))
    weights = {a["sleeve"]: a["weight"] for a in r["allocation"]}
    assert sum(weights.values()) == pytest.approx(100, abs=0.1)
    assert r["years_to_goal"] == 15
    assert r["risk_category"] is None  # no risk profile: treated as moderate
    assert r["equity_share"] == pytest.approx(60, abs=0.1)
    assert weights["mid_small_cap"] <= 30.1  # at most half of the equity
    assert r["inputs"]["fund_model"] is None  # no ranker trained: Sharpe fallback
    assert {f["basis"] for f in r["funds"]} == {"sharpe"}
    assert sum(f["weight"] for f in r["funds"]) == pytest.approx(100, abs=0.2)
    large = [f for f in r["funds"] if f["sleeve"] == "large_cap"]
    assert [f["amc"] for f in large] == ["AMC 2", "AMC 1"]  # best Sharpe first
    assert r["reasons"][0].startswith("Your moderate (no risk profile yet) risk profile")
    market_info = r["inputs"]["capital_market"]
    assert market_info["months"] >= 60
    assert len(market_info["correlation"]) == 4
    assert len(r["inputs"]["frontier"]) > 10
    assert r["inputs"]["goal_return"] == 10.0  # the goal's automatic return


def test_near_goal_is_mostly_short_term_debt(client, auth_headers, market):
    r = recommend(client, auth_headers, goal(client, auth_headers, target_year=THIS_YEAR + 1))
    weights = {a["sleeve"]: a["weight"] for a in r["allocation"]}
    assert r["equity_share"] == 0
    assert weights["short_debt"] == pytest.approx(100, abs=0.1)
    assert {f["sleeve"] for f in r["funds"]} == {"short_debt"}


def test_emergency_fund_stays_liquid(client, auth_headers, market):
    goal_id = goal(client, auth_headers, goal_type="emergency_fund", target_year=THIS_YEAR + 20)
    r = recommend(client, auth_headers, goal_id)
    assert r["equity_share"] == 0
    assert r["reasons"][0].startswith("An emergency fund must be available")


def test_picks_follow_the_fund_model_when_trained(client, auth_headers, market, db):
    model = registry.register(
        db, name="fund_ranker", version=1, algorithm="LightGBM", params={}, metrics={},
        data_start=date(2020, 1, 1), data_end=date(2025, 12, 1),
    )  # fmt: skip
    for rank, fund in enumerate(reversed(market["Large Cap Fund"]), start=1):
        db.add(
            FundPrediction(
                model_id=model.id, fund_id=fund.id, as_of=date(2025, 12, 1),
                peer_group="large_cap", predicted_quartile=1, prob_top=0.4 - rank / 100,
                probabilities=[0.4, 0.2, 0.2, 0.2], expected_quartile=2.0 + rank / 10,
                peer_rank=rank, peer_size=3,
                factors=[{"feature": "peer_ret_12m", "label": "12-month return vs peers",
                          "value": 0.9, "contribution": 0.3}],
            )
        )  # fmt: skip
    db.commit()
    r = recommend(client, auth_headers, goal(client, auth_headers))
    assert r["inputs"]["fund_model"] == "fund_ranker v1"
    large = [f for f in r["funds"] if f["sleeve"] == "large_cap"]
    assert [f["peer_label"] for f in large] == ["Large cap", "Large cap"]
    assert large[0]["name"].startswith("Large Cap Fund 2")  # rank 1
    assert "Ranked 1 of 3 large cap funds" in large[0]["reason"]
    # Sleeves the model does not cover get no picks, and the notes say so.
    assert any("No eligible" in note for note in r["inputs"]["notes"])


# --- Storage ------------------------------------------------------------------------------------


def test_recommendations_are_kept_as_history(client, auth_headers, market, db):
    goal_id = goal(client, auth_headers)
    first = recommend(client, auth_headers, goal_id)
    second = recommend(client, auth_headers, goal_id)
    history = client.get(f"/api/goals/{goal_id}/recommendations", headers=auth_headers).json()
    assert [h["id"] for h in history] == [second["id"], first["id"]]
    assert history[0]["funds"] == len(second["funds"])
    latest = client.get(f"/api/goals/{goal_id}/recommendations/latest", headers=auth_headers)
    assert latest.json()["id"] == second["id"]
    old = client.get(f"/api/goals/{goal_id}/recommendations/{first['id']}", headers=auth_headers)
    assert old.json() == first  # a snapshot: exactly what was shown
    url = f"/api/goals/{goal_id}/recommendations/999999"
    assert client.get(url, headers=auth_headers).status_code == 404


def test_no_recommendation_yet(client, auth_headers):
    goal_id = goal(client, auth_headers)
    url = f"/api/goals/{goal_id}/recommendations/latest"
    assert client.get(url, headers=auth_headers).status_code == 404


def test_deleting_the_goal_deletes_its_recommendations(client, auth_headers, market, db):
    goal_id = goal(client, auth_headers)
    recommend(client, auth_headers, goal_id)
    client.delete(f"/api/goals/{goal_id}", headers=auth_headers)
    assert db.scalar(select(func.count()).select_from(Recommendation)) == 0
    assert db.get(Goal, goal_id) is None
