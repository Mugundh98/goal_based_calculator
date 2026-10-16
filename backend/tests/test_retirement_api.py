"""API tests for the retirement planner (real test database)."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Goal, RetirementPlan, User
from tests.conftest import login_headers
from tests.test_profile_api import PROFILE

TODAY = date.today()
THIS_YEAR = TODAY.year
# Born on 1 January 34 years ago: exactly 34 all year, as in the worked example.
PROFILE_34 = {**PROFILE, "date_of_birth": f"{THIS_YEAR - 34}-01-01"}

PLAN = {
    "retirement_age": 60,
    "life_expectancy": 85,
    "monthly_expense": 40000,
    "inflation_rate": 6,
    "pre_retirement_return": 10,
    "post_retirement_return": 8,
    "current_savings": 500000,
    "monthly_sip": 10000,
}


@pytest.fixture
def headers(client, auth_headers):
    client.put("/api/profile", json=PROFILE_34, headers=auth_headers)
    return auth_headers


def save(client, headers, **changes):
    response = client.put("/api/retirement", json={**PLAN, **changes}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def retirement_goal(client, headers):
    goals = client.get("/api/goals", headers=headers).json()
    return next(g for g in goals if g["goal_type"] == "retirement")


# --- Access -------------------------------------------------------------------------------------


def test_requires_login(client):
    assert client.get("/api/retirement").status_code == 401
    assert client.put("/api/retirement", json=PLAN).status_code == 401
    assert client.post("/api/retirement/calculate", json=PLAN).status_code == 401
    assert client.post("/api/retirement/simulate", json=PLAN).status_code == 401


def test_profile_required(client, auth_headers):
    for method, url in [("put", "/api/retirement"), ("post", "/api/retirement/calculate")]:
        response = getattr(client, method)(url, json=PLAN, headers=auth_headers)
        assert response.status_code == 409
        assert "profile" in response.json()["detail"]


def test_no_plan_yet(client, headers):
    assert client.get("/api/retirement", headers=headers).status_code == 404
    assert client.delete("/api/retirement", headers=headers).status_code == 404


# --- Calculation ------------------------------------------------------------------------------


def test_calculate_worked_example(client, headers, db):
    response = client.post("/api/retirement/calculate", json=PLAN, headers=headers)
    assert response.status_code == 200
    p = response.json()
    assert p["current_age"] == 34
    assert p["years_to_retirement"] == 26
    assert p["retirement_year"] == THIS_YEAR + 26
    assert p["retirement_years"] == 25
    assert p["first_monthly_withdrawal"] == 181975.32
    assert p["corpus_needed"] == 42505424.85
    assert p["corpus_needed_today"] == pytest.approx(9_343_118.66, abs=0.01)  # ÷ 1.06^26
    assert p["corpus_multiple"] == 19.46
    assert p["withdrawal_rate"] == 5.14
    assert p["bengen_corpus"] == pytest.approx(181975.32 * 12 * 25, abs=1)
    assert p["real_post_return"] == 1.89
    assert p["accumulation"]["required_sip"] == 26481
    assert p["accumulation"]["funded_percent"] == 46.4
    assert p["money_lasts_until"] == 70.2
    assert [y["age"] for y in p["lifetime"]] == list(range(34, 86))
    assert db.scalar(select(func.count()).select_from(RetirementPlan)) == 0  # nothing saved


def test_automatic_pre_retirement_return(client, headers):
    auto = {**PLAN, "pre_retirement_return": None}
    p = client.post("/api/retirement/calculate", json=auto, headers=headers).json()
    assert (p["pre_retirement_return_used"], p["pre_retirement_return_source"]) == (10, "default")
    soon = client.post(
        "/api/retirement/calculate", json={**auto, "retirement_age": 36}, headers=headers
    ).json()
    assert (soon["pre_retirement_return_used"], soon["pre_retirement_return_source"]) == (
        7,
        "short_horizon",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"retirement_age": 34},  # already 34
        {"retirement_age": 30},
        {"life_expectancy": 60},  # not after retirement
        {"retirement_age": 40, "life_expectancy": 95},  # 55 years of retirement
        {"monthly_expense": 0},
        {"post_retirement_return": 31},
        {"inflation_rate": 21},
        {"retirement_age": 81},
    ],
)
def test_invalid_plans_rejected(client, headers, changes):
    response = client.post("/api/retirement/calculate", json={**PLAN, **changes}, headers=headers)
    assert response.status_code == 422


def test_retiring_before_the_current_age_explains_why(client, headers):
    response = client.put(
        "/api/retirement",
        json={**PLAN, "retirement_age": 33, "life_expectancy": 80},
        headers=headers,
    )
    assert response.status_code == 422
    assert "current age (34)" in response.json()["detail"]


# --- Saved plan and its goal --------------------------------------------------------------


def test_save_creates_plan_and_retirement_goal(client, headers):
    plan = save(client, headers)
    assert plan["projection"]["corpus_needed"] == 42505424.85
    assert client.get("/api/retirement", headers=headers).json()["goal_id"] == plan["goal_id"]

    goal = retirement_goal(client, headers)
    assert goal["id"] == plan["goal_id"]
    assert goal["name"] == "Retirement at 60"
    assert goal["priority"] == 1
    assert goal["target_year"] == THIS_YEAR + 26
    assert goal["monthly_sip"] == 10000
    # The ordinary goal maths (Phase 3) reproduces the planner: same corpus, same SIP.
    assert goal["projection"]["inflated_target"] == pytest.approx(42505424.85, abs=1)
    assert goal["projection"]["required_sip"] == plan["projection"]["accumulation"]["required_sip"]


def test_save_is_idempotent(client, headers, db):
    save(client, headers)
    save(client, headers, monthly_expense=50000, retirement_age=58)
    assert db.scalar(select(func.count()).select_from(RetirementPlan)) == 1
    assert db.scalar(select(func.count()).select_from(Goal)) == 1
    plan = client.get("/api/retirement", headers=headers).json()
    assert (plan["monthly_expense"], plan["retirement_age"]) == (50000, 58)
    assert retirement_goal(client, headers)["name"] == "Retirement at 58"


def test_saved_plan_reads_back_its_inputs(client, headers):
    save(client, headers, step_up_rate=10, pre_retirement_return=None)
    plan = client.get("/api/retirement", headers=headers).json()
    for field in ("retirement_age", "life_expectancy", "monthly_expense", "current_savings"):
        assert plan[field] == PLAN[field]
    assert plan["step_up_rate"] == 10
    assert plan["pre_retirement_return"] is None


def test_retirement_goal_cannot_be_edited_on_the_goals_page(client, headers):
    save(client, headers)
    goal = retirement_goal(client, headers)
    body = {
        "goal_type": "retirement",
        "name": "x",
        "target_amount": 1,
        "target_year": THIS_YEAR + 5,
    }
    response = client.put(f"/api/goals/{goal['id']}", json=body, headers=headers)
    assert response.status_code == 409
    assert "retirement planner" in response.json()["detail"]


def test_delete_removes_plan_and_goal(client, headers, db):
    save(client, headers)
    assert client.delete("/api/retirement", headers=headers).status_code == 204
    assert client.get("/api/retirement", headers=headers).status_code == 404
    assert db.scalar(select(func.count()).select_from(Goal)) == 0


def test_deleting_the_goal_deletes_the_plan(client, headers, db):
    plan = save(client, headers)
    assert client.delete(f"/api/goals/{plan['goal_id']}", headers=headers).status_code == 204
    assert db.scalar(select(func.count()).select_from(RetirementPlan)) == 0


def test_new_date_of_birth_moves_the_retirement_year(client, headers):
    save(client, headers)
    client.put(
        "/api/profile",
        json={**PROFILE_34, "date_of_birth": f"{THIS_YEAR - 40}-01-01"},
        headers=headers,
    )
    assert retirement_goal(client, headers)["target_year"] == THIS_YEAR + 20
    assert client.get("/api/retirement", headers=headers).json()["projection"]["current_age"] == 40


def test_users_only_see_their_own_plan(client, headers):
    save(client, headers)
    other = login_headers(client, "other@example.com")
    assert client.get("/api/retirement", headers=other).status_code == 404


def test_database_rejects_life_expectancy_before_retirement(client, headers, db):
    plan = save(client, headers)
    stored = db.get(RetirementPlan, db.scalar(select(RetirementPlan.id)))
    assert stored.goal_id == plan["goal_id"]
    stored.life_expectancy = 50
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_deleting_user_deletes_plan(client, headers, db):
    save(client, headers)
    db.delete(db.scalar(select(User).where(User.email == "user@example.com")))
    db.commit()
    assert db.scalar(select(func.count()).select_from(RetirementPlan)) == 0


# --- Simulation ---------------------------------------------------------------------------------


def test_simulate_lifetime(client, headers):
    body = {**PLAN, "model": "normal", "paths": 1000}
    response = client.post("/api/retirement/simulate", json=body, headers=headers)
    assert response.status_code == 200, response.text
    s = response.json()
    assert 0 <= s["success_probability"] <= 100
    assert [x["age"] for x in s["survival"]] == list(range(60, 86))
    assert s["survival"][0]["probability"] == 100
    assert s["survival"][-1]["probability"] == s["success_probability"]
    assert [b["age"] for b in s["bands"]] == list(range(34, 86))
    assert s["bands"][0]["calendar_year"] == THIS_YEAR
    assert s["corpus_target"] == 42505424.85
    sips = [x["monthly_sip"] for x in s["required_sip"]]
    assert sips == sorted(sips)
    assert s["before_retirement"]["equity_percent"] == 50  # 10% = half equity (ADR-008)
    assert s["after_retirement"]["equity_percent"] == pytest.approx(16.7)
    assert s["history"] is None  # no market data in the test database: assumed volatility


def test_simulation_is_reproducible(client, headers):
    body = {**PLAN, "model": "normal", "paths": 500, "seed": 42}
    first = client.post("/api/retirement/simulate", json=body, headers=headers).json()
    again = client.post("/api/retirement/simulate", json=body, headers=headers).json()
    assert first["bands"] == again["bands"]


def test_history_models_need_market_data(client, headers):
    body = {**PLAN, "model": "bootstrap", "paths": 500}
    assert client.post("/api/retirement/simulate", json=body, headers=headers).status_code == 409
