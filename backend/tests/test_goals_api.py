"""API tests for goals (real test database)."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.finance.risk_profile import QUESTIONS
from app.models import Goal, User
from tests.conftest import login_headers
from tests.test_profile_api import PROFILE

THIS_YEAR = date.today().year

# The worked example from the Phase 3 document, with a custom 12% return.
EDUCATION = {
    "goal_type": "education",
    "name": "Ananya's engineering degree",
    "target_amount": 2000000,
    "target_year": THIS_YEAR + 15,
    "priority": 1,
    "inflation_rate": 10,
    "expected_return": 12,
    "current_savings": 200000,
    "monthly_sip": 15000,
}
CAR = {"goal_type": "car", "name": "New car", "target_amount": 800000, "target_year": THIS_YEAR + 4}


def create(client, headers, **overrides):
    response = client.post("/api/goals", json={**EDUCATION, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_goals_require_login(client):
    assert client.get("/api/goals").status_code == 401
    assert client.post("/api/goals", json=EDUCATION).status_code == 401
    assert client.post("/api/goals/calculate", json=EDUCATION).status_code == 401


def test_create_returns_goal_with_projection(client, auth_headers):
    goal = create(client, auth_headers)
    assert goal["name"] == "Ananya's engineering degree"
    p = goal["projection"]
    assert p["years_to_goal"] == 15
    assert p["inflated_target"] == pytest.approx(8354496.34)
    assert p["required_sip"] == 15254
    assert p["shortfall"] == pytest.approx(120812.20)
    assert p["on_track"] is False
    assert p["expected_return_used"] == 12
    assert p["expected_return_source"] == "custom"
    assert p["real_return"] == pytest.approx(1.82)  # percent


def test_defaults_applied(client, auth_headers):
    car = client.post("/api/goals", json=CAR, headers=auth_headers).json()
    assert car["priority"] == 2
    assert car["inflation_rate"] == 6
    assert car["current_savings"] == 0
    assert car["monthly_sip"] == 0
    assert car["step_up_rate"] == 0
    assert car["expected_return"] is None  # automatic


def test_automatic_return_without_risk_profile(client, auth_headers):
    p = create(client, auth_headers, expected_return=None)["projection"]
    assert (p["expected_return_used"], p["expected_return_source"]) == (10, "default")


def test_automatic_return_follows_latest_risk_profile(client, auth_headers):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    lowest = {q.id: q.options[0].id for q in QUESTIONS}  # → conservative
    client.post("/api/risk/assessments", json={"answers": lowest}, headers=auth_headers)
    goal = create(client, auth_headers, expected_return=None)
    p = goal["projection"]
    assert (p["expected_return_used"], p["expected_return_source"]) == (8, "risk_profile")

    # Retaking the questionnaire changes the projection of the SAME stored goal.
    middle = {q.id: "c" for q in QUESTIONS}  # → moderate
    client.post("/api/risk/assessments", json={"answers": middle}, headers=auth_headers)
    again = client.get(f"/api/goals/{goal['id']}", headers=auth_headers).json()["projection"]
    assert again["expected_return_used"] == 10


def test_short_horizon_uses_cautious_return(client, auth_headers):
    p = create(client, auth_headers, expected_return=None, target_year=THIS_YEAR + 2)["projection"]
    assert (p["expected_return_used"], p["expected_return_source"]) == (7, "short_horizon")


def test_list_sorted_by_priority_then_year(client, auth_headers):
    create(client, auth_headers, name="Low", priority=3, target_year=THIS_YEAR + 2)
    create(client, auth_headers, name="High later", priority=1, target_year=THIS_YEAR + 20)
    create(client, auth_headers, name="High sooner", priority=1, target_year=THIS_YEAR + 5)
    names = [g["name"] for g in client.get("/api/goals", headers=auth_headers).json()]
    assert names == ["High sooner", "High later", "Low"]


def test_update_replaces_goal(client, auth_headers):
    goal = create(client, auth_headers)
    response = client.put(
        f"/api/goals/{goal['id']}", json={**EDUCATION, "monthly_sip": 15254}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["projection"]["on_track"] is True


def test_delete_goal(client, auth_headers):
    goal = create(client, auth_headers)
    assert client.delete(f"/api/goals/{goal['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/goals/{goal['id']}", headers=auth_headers).status_code == 404
    assert client.get("/api/goals", headers=auth_headers).json() == []


def test_other_users_goals_are_invisible(client, auth_headers):
    goal = create(client, auth_headers)
    other = login_headers(client, "other@example.com")
    url = f"/api/goals/{goal['id']}"
    assert client.get(url, headers=other).status_code == 404
    assert client.put(url, json=EDUCATION, headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.get("/api/goals", headers=other).json() == []
    assert client.get(url, headers=auth_headers).status_code == 200  # still there


def test_money_keeps_paise(client, auth_headers):
    goal = create(client, auth_headers, current_savings=1234.56, inflation_rate=7.25)
    assert goal["current_savings"] == 1234.56
    assert goal["inflation_rate"] == 7.25


def test_calculate_does_not_save(client, auth_headers, db):
    response = client.post("/api/goals/calculate", json=EDUCATION, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["required_sip"] == 15254
    assert db.scalar(select(func.count()).select_from(Goal)) == 0


def test_calculate_needs_only_the_numbers(client, auth_headers):
    numbers = {"target_amount": 500000, "target_year": THIS_YEAR + 5}
    response = client.post("/api/goals/calculate", json=numbers, headers=auth_headers)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "field, value",
    [
        ("target_year", THIS_YEAR),  # must be in the future
        ("target_year", THIS_YEAR - 1),
        ("target_year", THIS_YEAR + 61),
        ("target_amount", 0),
        ("target_amount", -5),
        ("monthly_sip", -1),
        ("current_savings", 10.555),
        ("inflation_rate", 21),
        ("expected_return", 31),
        ("step_up_rate", 51),
        ("priority", 4),
        ("goal_type", "yacht"),
        ("name", "   "),
        ("name", "x" * 101),
    ],
)
def test_invalid_goal_rejected(client, auth_headers, field, value):
    response = client.post("/api/goals", json={**EDUCATION, field: value}, headers=auth_headers)
    assert response.status_code == 422


def test_database_rejects_invalid_priority(client, auth_headers, db):
    """CHECK constraints protect the data even if the API validation is bypassed."""
    user_id = client.get("/api/auth/me", headers=auth_headers).json()["id"]
    db.add(
        Goal(
            user_id=user_id,
            goal_type="car",
            name="x",
            target_amount=1,
            target_year=2040,
            priority=9,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_deleting_user_deletes_goals(client, auth_headers, db):
    create(client, auth_headers)
    user = db.scalar(select(User).where(User.email == "user@example.com"))
    db.delete(user)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Goal)) == 0
