"""API tests for Monte Carlo simulations (real test database)."""

from datetime import date
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Fund, Goal, IndexHistory, NavHistory, Simulation, SimulationResult, User
from app.services.simulations import EQUITY_INDEX
from tests.conftest import login_headers
from tests.test_goals_api import THIS_YEAR, create

MODELS = ["normal", "bootstrap", "garch", "hmm"]
FAST = {"paths": 1000}


def month_ends(start: date, count: int) -> list[date]:
    days = []
    year, month = start.year, start.month
    for _ in range(count):
        days.append(date(year, month, 28))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return days


@pytest.fixture
def market(db):
    """10 years of synthetic month-end data: the Nifty 500 and three bond funds."""
    generator = np.random.default_rng(0)
    days = month_ends(date(2016, 1, 1), 121)
    closes = 10_000 * np.exp(np.cumsum(generator.normal(0.009, 0.05, len(days))))
    db.add_all(
        IndexHistory(symbol=EQUITY_INDEX, trade_date=day, close=Decimal(f"{close:.4f}"))
        for day, close in zip(days, closes, strict=True)
    )
    for code in (900001, 900002, 900003):
        fund = Fund(
            scheme_code=code,
            name=f"Test Corporate Bond Fund {code}",
            amc="Test AMC",
            scheme_type="Open Ended",
            category="Corporate Bond Fund",
            asset_class="debt",
            plan="direct",
            option="growth",
            latest_nav_date=days[-1],
        )
        db.add(fund)
        db.flush()
        navs = 10 * np.exp(np.cumsum(generator.normal(0.006, 0.006, len(days))))
        db.add_all(
            NavHistory(fund_id=fund.id, nav_date=day, nav=Decimal(f"{nav:.8f}"))
            for day, nav in zip(days, navs, strict=True)
        )
    db.commit()


def simulate(client, headers, goal_id, **body):
    return client.post(f"/api/goals/{goal_id}/simulate", json={**FAST, **body}, headers=headers)


def save(client, headers, goal_id, **body):
    body = {**FAST, "model": "normal", **body}
    return client.post(f"/api/goals/{goal_id}/simulations", json=body, headers=headers)


def test_simulations_require_login(client):
    assert client.post("/api/goals/1/simulate", json={}).status_code == 401
    assert client.post("/api/goals/1/simulations", json={}).status_code == 401
    assert client.get("/api/goals/1/simulations").status_code == 401
    assert client.get("/api/simulations/1").status_code == 401


def test_simulate_worked_example(client, auth_headers, market):
    goal = create(client, auth_headers)
    response = simulate(client, auth_headers, goal["id"], model="bootstrap")
    assert response.status_code == 200, response.text
    result = response.json()

    inputs = result["inputs"]
    assert inputs["years"] == 15
    assert inputs["target_year"] == THIS_YEAR + 15
    assert inputs["inflated_target"] == pytest.approx(8354496.34)
    assert (inputs["expected_return"], inputs["expected_return_source"]) == (12, "custom")
    # 12% = (12 - 7) / (13 - 7) = 83.3% equity
    assert (inputs["equity_percent"], inputs["equity_source"]) == (83.3, "implied")

    # The Phase 3 numbers are reported alongside for comparison.
    assert result["deterministic"] == {
        "projected_value": goal["projection"]["projected_value"],
        "funded_percent": 98.5,
        "on_track": False,
        "required_sip": 15254,
    }
    assert 0 < result["success_probability"] < 100
    assert result["model"] == "bootstrap"
    assert result["paths"] == 1000
    assert result["seed"] == 2026
    assert [r["probability"] for r in result["required_sip"]] == [50, 75, 90]
    sips = [r["monthly_sip"] for r in result["required_sip"]]
    assert sips == sorted(sips)

    bands = result["bands"]
    assert [b["year"] for b in bands] == list(range(16))
    assert bands[0]["calendar_year"] == THIS_YEAR
    assert bands[0]["p50"] == 200000
    assert bands[-1]["deterministic"] == pytest.approx(goal["projection"]["projected_value"])
    for band in bands:
        assert band["p10"] <= band["p25"] <= band["p50"] <= band["p75"] <= band["p90"]
    assert result["final"]["p50"] == bands[-1]["p50"]

    history = result["history"]
    assert history["months"] == 119  # Feb 2016 .. Dec 2025; the latest month is left out
    assert history["start"] == "2016-02-01"
    assert "Nifty 500" in history["equity_source"]
    assert result["annual_volatility"] > 0
    assert result["model_details"] == {"block_months": 12, "history_months": 119}


@pytest.mark.parametrize("model", MODELS)
def test_every_model_runs(client, auth_headers, market, model):
    goal = create(client, auth_headers)
    result = simulate(client, auth_headers, goal["id"], model=model).json()
    assert result["model"] == model
    assert 0 <= result["success_probability"] <= 100
    assert result["model_details"]


def test_results_are_reproducible_with_the_seed(client, auth_headers, market):
    goal = create(client, auth_headers)
    first = simulate(client, auth_headers, goal["id"], seed=7).json()
    again = simulate(client, auth_headers, goal["id"], seed=7).json()
    other = simulate(client, auth_headers, goal["id"], seed=8).json()
    for result in (first, again, other):
        del result["elapsed_ms"]
    assert first == again
    assert first["bands"] != other["bands"]


def test_what_if_overrides(client, auth_headers, market):
    goal = create(client, auth_headers)
    base = simulate(client, auth_headers, goal["id"]).json()

    more_sip = simulate(client, auth_headers, goal["id"], overrides={"monthly_sip": 25000}).json()
    assert more_sip["inputs"]["monthly_sip"] == 25000
    assert more_sip["success_probability"] > base["success_probability"]

    later = simulate(
        client, auth_headers, goal["id"], overrides={"target_year": THIS_YEAR + 20}
    ).json()
    assert later["inputs"]["years"] == 20
    assert len(later["bands"]) == 21

    # Choosing the allocation sets the return: 30% equity = 7% + 0.3 x 6% = 8.8%.
    mix = simulate(client, auth_headers, goal["id"], overrides={"equity_percent": 30}).json()
    assert mix["inputs"]["equity_percent"] == 30
    assert mix["inputs"]["equity_source"] == "override"
    assert (mix["inputs"]["expected_return"], mix["inputs"]["expected_return_source"]) == (
        8.8,
        "allocation",
    )
    assert mix["annual_volatility"] < base["annual_volatility"]

    step_up = simulate(client, auth_headers, goal["id"], overrides={"step_up_rate": 10}).json()
    assert step_up["inputs"]["step_up_rate"] == 10
    assert step_up["deterministic"]["on_track"] is True

    # The saved goal itself is unchanged.
    stored = client.get(f"/api/goals/{goal['id']}", headers=auth_headers).json()
    assert stored["monthly_sip"] == 15000


def test_automatic_return_gives_the_matching_allocation(client, auth_headers, market):
    goal = create(client, auth_headers, expected_return=None)
    inputs = simulate(client, auth_headers, goal["id"]).json()["inputs"]
    assert (inputs["expected_return"], inputs["expected_return_source"]) == (10, "default")
    assert inputs["equity_percent"] == 50


def test_preview_saves_nothing(client, auth_headers, market, db):
    goal = create(client, auth_headers)
    simulate(client, auth_headers, goal["id"])
    assert db.scalar(select(func.count()).select_from(Simulation)) == 0


@pytest.mark.parametrize(
    "body",
    [
        {"model": "random_walk"},
        {"paths": 100},
        {"paths": 50000},
        {"seed": -1},
        {"overrides": {"target_year": THIS_YEAR}},
        {"overrides": {"target_year": THIS_YEAR + 61}},
        {"overrides": {"equity_percent": 101}},
        {"overrides": {"monthly_sip": -5}},
        {"overrides": {"step_up_rate": 60}},
    ],
)
def test_invalid_requests(client, auth_headers, market, body):
    goal = create(client, auth_headers)
    assert simulate(client, auth_headers, goal["id"], **body).status_code == 422


def test_without_market_data_only_the_normal_model_runs(client, auth_headers):
    goal = create(client, auth_headers)
    normal = simulate(client, auth_headers, goal["id"], model="normal").json()
    assert normal["history"] is None
    assert normal["model_details"]["source"] == "assumption"
    # 83.3% equity: sqrt((0.833 x 18%)^2 + (0.167 x 3%)^2) = 15.01%
    assert normal["annual_volatility"] == pytest.approx(15.01, abs=0.01)

    response = simulate(client, auth_headers, goal["id"], model="garch")
    assert response.status_code == 409
    assert "market data" in response.json()["detail"]

    comparison = client.post(
        f"/api/goals/{goal['id']}/simulate/compare", json=FAST, headers=auth_headers
    ).json()
    assert [m["model"] for m in comparison["models"]] == ["normal"]


def test_due_goal_cannot_be_simulated(client, auth_headers, db):
    goal = create(client, auth_headers)
    db.get(Goal, goal["id"]).target_year = THIS_YEAR  # cannot be entered through the API
    db.commit()
    response = simulate(client, auth_headers, goal["id"], model="normal")
    assert response.status_code == 409
    assert "due" in response.json()["detail"]


def test_compare_runs_all_models_on_the_same_inputs(client, auth_headers, market):
    goal = create(client, auth_headers)
    response = client.post(
        f"/api/goals/{goal['id']}/simulate/compare",
        json={**FAST, "overrides": {"monthly_sip": 20000}},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    comparison = response.json()
    assert [m["model"] for m in comparison["models"]] == MODELS
    assert comparison["inputs"]["monthly_sip"] == 20000
    assert comparison["history"]["months"] == 119
    for model in comparison["models"]:
        single = simulate(
            client, auth_headers, goal["id"], model=model["model"], overrides={"monthly_sip": 20000}
        ).json()
        assert model["success_probability"] == single["success_probability"]
        assert model["required_sip_90"] == single["required_sip"][2]["monthly_sip"]


def test_save_list_read_and_delete_runs(client, auth_headers, market):
    goal = create(client, auth_headers)
    url = f"/api/goals/{goal['id']}/simulations"
    first = client.post(url, json={**FAST, "model": "normal"}, headers=auth_headers)
    assert first.status_code == 201, first.text
    second = client.post(
        url,
        json={**FAST, "model": "hmm", "overrides": {"monthly_sip": 20000}},
        headers=auth_headers,
    ).json()

    # Reading a saved run gives back exactly what was returned when it was made.
    saved = first.json()
    read = client.get(f"/api/simulations/{saved['id']}", headers=auth_headers).json()
    assert read == saved
    preview = simulate(client, auth_headers, goal["id"], model="normal").json()
    for field in ("success_probability", "bands", "final", "inputs", "model_details"):
        assert saved[field] == preview[field]

    runs = client.get(url, headers=auth_headers).json()
    assert [r["id"] for r in runs] == [second["id"], saved["id"]]  # newest first
    assert runs[0]["model"] == "hmm"
    assert runs[0]["monthly_sip"] == 20000
    assert runs[0]["success_probability"] == second["success_probability"]
    assert runs[0]["median_final"] == second["final"]["p50"]
    assert "bands" not in runs[0]

    assert client.delete(f"/api/simulations/{saved['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/simulations/{saved['id']}", headers=auth_headers).status_code == 404
    assert len(client.get(url, headers=auth_headers).json()) == 1


def test_other_users_simulations_are_invisible(client, auth_headers, market):
    goal = create(client, auth_headers)
    run = save(client, auth_headers, goal["id"]).json()
    other = login_headers(client, "other@example.com")
    assert simulate(client, other, goal["id"]).status_code == 404
    assert client.get(f"/api/goals/{goal['id']}/simulations", headers=other).status_code == 404
    assert client.get(f"/api/simulations/{run['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/simulations/{run['id']}", headers=other).status_code == 404


def test_deleting_a_goal_deletes_its_runs(client, auth_headers, market, db):
    goal = create(client, auth_headers)
    save(client, auth_headers, goal["id"])
    assert db.scalar(select(func.count()).select_from(SimulationResult)) == 1
    client.delete(f"/api/goals/{goal['id']}", headers=auth_headers)
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Simulation)) == 0
    assert db.scalar(select(func.count()).select_from(SimulationResult)) == 0


def test_database_rejects_impossible_values(db):
    user = User(email="db@example.com", password_hash="x", full_name="DB")
    db.add(user)
    db.flush()
    goal = Goal(user_id=user.id, goal_type="car", name="Car", target_amount=1, target_year=2040)
    db.add(goal)
    db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(Simulation(goal_id=goal.id, model="crystal_ball", parameters={}))
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            simulation = Simulation(goal_id=goal.id, model="normal", parameters={})
            simulation.result = SimulationResult(
                success_probability=150,
                median_final=0,
                final_percentiles={},
                required_sip=[],
                bands=[],
                elapsed_ms=0,
            )
            db.add(simulation)
