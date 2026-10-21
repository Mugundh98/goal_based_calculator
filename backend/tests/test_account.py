"""The account page and "forgot password" by security question (1.2)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditLog
from app.schemas.auth import SECURITY_QUESTIONS
from app.services import auth as service
from tests.conftest import login_headers

QUESTION = SECURITY_QUESTIONS[0]


def register(client, email="asha@example.com", password="secret123", **extra):
    body = {"email": email, "password": password, "full_name": "Asha Rao"} | extra
    return client.post("/api/auth/register", json=body)


def login(client, email, password):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def reset(client, email, answer, new_password="newpass456"):
    return client.post(
        "/api/auth/forgot-password/reset",
        json={"email": email, "answer": answer, "new_password": new_password},
    )


def test_sign_up_with_a_security_question(client):
    assert client.get("/api/auth/security-questions").json() == list(SECURITY_QUESTIONS)
    response = register(client, security_question=QUESTION, security_answer="Delhi Public School")
    assert response.status_code == 201
    assert response.json()["security_question"] == QUESTION
    assert "security_answer" not in response.text and "hash" not in response.text

    half = register(client, email="b@example.com", security_question=QUESTION)
    assert half.status_code == 422 and "both" in half.text
    made_up = register(
        client, email="c@example.com", security_question="Your PIN?", security_answer="1234"
    )
    assert made_up.status_code == 422 and "listed" in made_up.text


def test_name_and_password_changes(client, db):
    headers = login_headers(client, "user@example.com")
    renamed = client.patch("/api/auth/me", json={"full_name": "  Ravi Kumar "}, headers=headers)
    assert renamed.status_code == 200 and renamed.json()["full_name"] == "Ravi Kumar"
    assert renamed.json()["email"] == "user@example.com"

    wrong = {"current_password": "nope", "new_password": "better789"}
    response = client.put("/api/auth/password", json=wrong, headers=headers)
    assert response.status_code == 400 and "current password" in response.json()["detail"]
    weak = {"current_password": "secret123", "new_password": "onlyletters"}
    assert client.put("/api/auth/password", json=weak, headers=headers).status_code == 422

    good = {"current_password": "secret123", "new_password": "better789"}
    assert client.put("/api/auth/password", json=good, headers=headers).status_code == 204
    assert login(client, "user@example.com", "secret123").status_code == 401
    assert login(client, "user@example.com", "better789").status_code == 200
    actions = set(db.scalars(select(AuditLog.action)))
    assert {"auth.name.change", "auth.password.change"} <= actions


def test_set_the_question_later_needs_the_password(client):
    headers = login_headers(client, "user@example.com")
    body = {"current_password": "wrong", "question": QUESTION, "answer": "Mumbai"}
    assert client.put("/api/auth/security-question", json=body, headers=headers).status_code == 400
    body["current_password"] = "secret123"
    response = client.put("/api/auth/security-question", json=body, headers=headers)
    assert response.status_code == 200 and response.json()["security_question"] == QUESTION
    assert client.get("/api/auth/me", headers=headers).json()["security_question"] == QUESTION


def test_forgot_password_with_the_right_answer(client, db):
    register(client, security_question=QUESTION, security_answer="Delhi Public School")
    asked = client.post("/api/auth/forgot-password/question", json={"email": "ASHA@example.com"})
    assert asked.json() == {"question": QUESTION}

    wrong = reset(client, "asha@example.com", "Kendriya Vidyalaya")
    assert wrong.status_code == 400 and "does not match" in wrong.json()["detail"]
    assert login(client, "asha@example.com", "newpass456").status_code == 401

    # Capitals and extra spaces do not matter.
    assert reset(client, "asha@example.com", "  delhi   PUBLIC school ").status_code == 204
    assert login(client, "asha@example.com", "newpass456").status_code == 200
    actions = list(db.scalars(select(AuditLog.action).order_by(AuditLog.id)))
    assert actions[-4:] == [
        "auth.password_reset_failed",
        "auth.login_failed",  # the old-password check above
        "auth.password_reset",
        "auth.login",
    ]


def test_the_question_step_does_not_reveal_accounts(client):
    login_headers(client, "noquestion@example.com")  # an account without a question

    def question(email):
        return client.post("/api/auth/forgot-password/question", json={"email": email}).json()

    stranger = question("nobody@example.com")
    assert stranger["question"] in SECURITY_QUESTIONS
    assert question("nobody@example.com") == stranger  # the same every time
    assert question("noquestion@example.com")["question"] in SECURITY_QUESTIONS
    # Nothing can be reset without a stored answer, whatever is typed.
    for email in ("nobody@example.com", "noquestion@example.com"):
        assert reset(client, email, "anything").status_code == 400


def test_five_wrong_answers_lock_resets_for_an_hour(client, db):
    register(client, security_question=QUESTION, security_answer="Delhi Public School")
    for _ in range(service.RESET_ATTEMPTS):
        assert reset(client, "asha@example.com", "guess").status_code == 400
    locked = reset(client, "asha@example.com", "Delhi Public School")
    assert locked.status_code == 429 and "an hour" in locked.json()["detail"]
    later = datetime.now(UTC) + service.RESET_WINDOW + timedelta(minutes=1)
    assert service.recent_failures(db, "asha@example.com", now=later) == 0
    failures = db.scalar(
        select(func.count()).where(AuditLog.action == "auth.password_reset_failed")
    )
    assert failures == service.RESET_ATTEMPTS  # the locked attempt was not even checked
