"""API tests for the financial profile and risk assessments (real test database)."""

from datetime import date

import pytest
from sqlalchemy import func, select

from app.finance.risk_profile import QUESTIONS
from app.models import FinancialProfile, RiskAssessment, User
from tests.conftest import login_headers

PROFILE = {
    "date_of_birth": "1992-04-10",
    "employment_type": "salaried",
    "monthly_income": 120000,
    "monthly_expenses": 60000,
    "monthly_emi": 25000,
    "current_savings": 300000,
    "existing_investments": 500000,
    "dependents": 2,
}
MIDDLE_ANSWERS = {q.id: "c" for q in QUESTIONS}


# --- Profile ----------------------------------------------------------------------------------


def test_profile_requires_login(client):
    assert client.get("/api/profile").status_code == 401
    assert client.put("/api/profile", json=PROFILE).status_code == 401


def test_profile_404_before_creation(client, auth_headers):
    assert client.get("/api/profile", headers=auth_headers).status_code == 404


def test_create_and_read_profile(client, auth_headers):
    saved = client.put("/api/profile", json=PROFILE, headers=auth_headers)
    assert saved.status_code == 200
    body = client.get("/api/profile", headers=auth_headers).json()
    assert body["monthly_income"] == 120000
    assert body["monthly_surplus"] == 35000  # 120000 - 60000 - 25000
    assert body["age"] == date.today().year - 1992 - (
        0 if (date.today().month, date.today().day) >= (4, 10) else 1
    )


def test_put_replaces_existing_profile(client, auth_headers, db):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    client.put("/api/profile", json={**PROFILE, "dependents": 0}, headers=auth_headers)
    assert client.get("/api/profile", headers=auth_headers).json()["dependents"] == 0
    count = db.scalar(select(func.count()).select_from(FinancialProfile))
    assert count == 1  # updated in place, not duplicated


def test_money_keeps_paise(client, auth_headers):
    client.put("/api/profile", json={**PROFILE, "monthly_income": 75000.55}, headers=auth_headers)
    assert client.get("/api/profile", headers=auth_headers).json()["monthly_income"] == 75000.55


@pytest.mark.parametrize(
    "field, value",
    [
        ("monthly_income", -1),
        ("monthly_expenses", 10.555),  # more than 2 decimal places
        ("dependents", 21),
        ("employment_type", "astronaut"),
        ("date_of_birth", "2015-01-01"),  # under 18
        ("date_of_birth", "1900-01-01"),  # implausible
    ],
)
def test_invalid_profile_rejected(client, auth_headers, field, value):
    response = client.put("/api/profile", json={**PROFILE, field: value}, headers=auth_headers)
    assert response.status_code == 422


def test_users_only_see_their_own_profile(client, auth_headers):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    other = login_headers(client, "other@example.com")
    assert client.get("/api/profile", headers=other).status_code == 404


# --- Risk assessments -------------------------------------------------------------------------


def test_questionnaire_hides_points(client, auth_headers):
    body = client.get("/api/risk/questionnaire", headers=auth_headers).json()
    assert body["version"] == "v1"
    assert len(body["questions"]) == 7
    option = body["questions"][0]["options"][0]
    assert set(option) == {"id", "text"}


def test_assessment_requires_profile(client, auth_headers):
    response = client.post(
        "/api/risk/assessments", json={"answers": MIDDLE_ANSWERS}, headers=auth_headers
    )
    assert response.status_code == 409


def test_assessment_scored_and_stored(client, auth_headers):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    response = client.post(
        "/api/risk/assessments", json={"answers": MIDDLE_ANSWERS}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["tolerance_score"] == 54  # 15 of 28 points ("c" on risk_word = 3)
    assert body["capacity_score"] == 72  # worked example in the Phase 2 document
    assert body["final_score"] == 54  # the lower of the two
    assert body["category"] == "moderate"
    assert len(body["capacity_breakdown"]) == 6
    assert "moderate" in body["explanation"]


def test_incomplete_answers_rejected(client, auth_headers):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    answers = dict(MIDDLE_ANSWERS)
    answers.pop("objective")
    response = client.post("/api/risk/assessments", json={"answers": answers}, headers=auth_headers)
    assert response.status_code == 422
    assert "objective" in response.json()["detail"]


def test_latest_and_history(client, auth_headers):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    assert client.get("/api/risk/assessments/latest", headers=auth_headers).status_code == 404

    low = {q.id: q.options[0].id for q in QUESTIONS}
    client.post("/api/risk/assessments", json={"answers": low}, headers=auth_headers)
    client.post("/api/risk/assessments", json={"answers": MIDDLE_ANSWERS}, headers=auth_headers)

    history = client.get("/api/risk/assessments", headers=auth_headers).json()
    assert [a["tolerance_score"] for a in history] == [54, 0]  # newest first
    latest = client.get("/api/risk/assessments/latest", headers=auth_headers).json()
    assert latest["id"] == history[0]["id"]


def test_assessment_is_a_snapshot(client, auth_headers):
    """Changing the profile later must not change a stored assessment."""
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    first = client.post(
        "/api/risk/assessments", json={"answers": MIDDLE_ANSWERS}, headers=auth_headers
    ).json()
    client.put("/api/profile", json={**PROFILE, "dependents": 5}, headers=auth_headers)
    stored = client.get("/api/risk/assessments", headers=auth_headers).json()[0]
    assert stored["capacity_score"] == first["capacity_score"]


def test_deleting_user_deletes_profile_and_assessments(client, auth_headers, db):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    client.post("/api/risk/assessments", json={"answers": MIDDLE_ANSWERS}, headers=auth_headers)
    db.delete(db.scalar(select(User).where(User.email == "user@example.com")))
    db.commit()
    assert db.scalar(select(func.count()).select_from(FinancialProfile)) == 0
    assert db.scalar(select(func.count()).select_from(RiskAssessment)) == 0
