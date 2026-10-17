"""Administration: role-based access, overview, user management, audit log, model versions."""

from contextlib import nullcontext
from datetime import date

import pytest
from sqlalchemy import select

from app import admin as admin_cli
from app.models import AuditLog, ChatMessage, ChatSession, MLModel, ToolCall, User
from tests.conftest import login_headers

THIS_YEAR = date.today().year


def make_admin(db, email):
    user = db.scalar(select(User).where(User.email == email))
    user.role = "admin"
    db.commit()


@pytest.fixture
def admin_headers(client, db):
    headers = login_headers(client, "admin@example.com")
    make_admin(db, "admin@example.com")
    return headers  # the role is read from the database on every request


def user_id(db, email):
    return db.scalar(select(User.id).where(User.email == email))


ADMIN_GETS = ["/api/admin/overview", "/api/admin/users", "/api/admin/audit",
              "/api/admin/audit/actions", "/api/admin/models"]  # fmt: skip


def test_only_admins_get_in(client, auth_headers):
    for path in ADMIN_GETS:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth_headers).status_code == 403
    assert client.patch("/api/admin/users/1", json={}, headers=auth_headers).status_code == 403
    assert client.post("/api/admin/models/1/activate", headers=auth_headers).status_code == 403


def test_overview_counts_users_activity_and_assistant_use(client, db, admin_headers, auth_headers):
    client.post("/api/goals", headers=auth_headers, json={
        "goal_type": "car", "name": "Car", "target_amount": 800_000, "target_year": THIS_YEAR + 3,
    })  # fmt: skip
    client.post("/api/auth/login", data={"username": "user@example.com", "password": "nope"})
    session = ChatSession(user_id=user_id(db, "user@example.com"))
    db.add(session)
    db.flush()
    answers = [
        ChatMessage(session_id=session.id, role="assistant", content="a", payload={}),
        ChatMessage(session_id=session.id, role="assistant", content="b",
                    payload={"ungrounded": ["7,224"]}),
        ChatMessage(session_id=session.id, role="assistant", content="c",
                    payload={"error": "rate_limit", "ungrounded": []}),
    ]  # fmt: skip
    db.add_all([ChatMessage(session_id=session.id, role="user", content="q"), *answers])
    db.flush()
    db.add_all([
        ToolCall(message_id=answers[0].id, tool="list_goals", arguments={}, result={},
                 status="ok", latency_ms=60),
        ToolCall(message_id=answers[1].id, tool="list_goals", arguments={}, result={},
                 status="error", latency_ms=100),
    ])  # fmt: skip
    db.commit()

    body = client.get("/api/admin/overview", headers=admin_headers).json()
    assert body["users"] == {"total": 2, "active": 2, "admins": 1, "new_last_7_days": 2}
    assert body["activity"]["goals"] == 1
    assert body["activity"]["logins_7_days"] == 2 and body["activity"]["failed_logins_7_days"] == 1
    assistant = body["assistant"]
    assert (assistant["questions_7_days"], assistant["answers_7_days"]) == (1, 3)
    assert assistant["fallback_answers_7_days"] == 1
    assert assistant["answers_with_ungrounded_numbers_7_days"] == 1
    assert assistant["tools"] == [{"tool": "list_goals", "calls": 2, "errors": 1,
                                   "average_ms": 80.0}]  # fmt: skip


def test_users_list_search_and_last_login(client, db, admin_headers, auth_headers):
    login_headers(client, "priya@example.com")
    body = client.get("/api/admin/users", headers=admin_headers).json()
    assert body["total"] == 3
    assert [u["email"] for u in body["items"]][0] == "priya@example.com"  # newest first
    found = client.get("/api/admin/users?q=PRIYA", headers=admin_headers).json()["items"]
    assert [u["email"] for u in found] == ["priya@example.com"]
    assert found[0]["last_login"] is not None and found[0]["goals"] == 0


def test_admin_can_promote_and_deactivate_others_but_not_themselves(client, db, admin_headers,
                                                                    auth_headers):  # fmt: skip
    target = user_id(db, "user@example.com")
    response = client.patch(f"/api/admin/users/{target}", json={"role": "admin"},
                            headers=admin_headers)  # fmt: skip
    assert response.status_code == 200 and response.json()["role"] == "admin"
    client.patch(f"/api/admin/users/{target}", json={"role": "user", "is_active": False},
                 headers=admin_headers)  # fmt: skip
    # The deactivated account is locked out at once, even with a valid token.
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 401
    updates = db.scalars(select(AuditLog).where(AuditLog.action == "admin.user.update")
                         .order_by(AuditLog.id)).all()  # fmt: skip
    assert updates[0].details["role"] == {"from": "user", "to": "admin"}
    assert updates[1].details["is_active"] == {"from": True, "to": False}
    assert updates[1].actor_email == "admin@example.com"

    me = user_id(db, "admin@example.com")
    for change in ({"role": "user"}, {"is_active": False}):
        response = client.patch(f"/api/admin/users/{me}", json=change, headers=admin_headers)
        assert response.status_code == 409
    assert (
        client.patch("/api/admin/users/999999", json={}, headers=admin_headers).status_code == 404
    )
    assert client.patch(f"/api/admin/users/{target}", json={"role": "owner"},
                        headers=admin_headers).status_code == 422  # fmt: skip


def test_audit_log_endpoint(client, db, admin_headers, auth_headers):
    client.post("/api/goals", headers=auth_headers, json={
        "goal_type": "car", "name": "Car", "target_amount": 800_000, "target_year": THIS_YEAR + 3,
    })  # fmt: skip
    body = client.get("/api/admin/audit?action=goal.", headers=admin_headers).json()
    assert body["total"] == 1
    [entry] = body["items"]
    assert (entry["action"], entry["description"], entry["details"]["name"]) == (
        "goal.create", "Goal created", "Car")  # fmt: skip
    mine = client.get(f"/api/admin/audit?actor_id={user_id(db, 'admin@example.com')}",
                      headers=admin_headers).json()  # fmt: skip
    assert {e["action"] for e in mine["items"]} == {"auth.register", "auth.login"}
    actions = client.get("/api/admin/audit/actions", headers=admin_headers).json()
    assert actions["report.download"] == "Plan report downloaded"


def test_model_versions_can_be_listed_and_rolled_back(client, db, admin_headers):
    old, new = (
        MLModel(name="fund_ranker", version=v, algorithm="LightGBM", params={},
                metrics={"rows": 100 * v, "evaluation": {"mae": 1.5}, "importance": [1, 2]},
                data_start=date(2015, 1, 31), data_end=date(2025, 12, 31), is_active=v == 2)
        for v in (1, 2)
    )  # fmt: skip
    db.add_all([old, new])
    db.commit()
    versions = client.get("/api/admin/models", headers=admin_headers).json()
    assert [(m["version"], m["is_active"]) for m in versions] == [(2, True), (1, False)]
    assert versions[0]["headline"] == {"rows": 200, "mae": 1.5}  # lists left out
    after = client.post(f"/api/admin/models/{old.id}/activate", headers=admin_headers).json()
    assert [(m["version"], m["is_active"]) for m in after] == [(2, False), (1, True)]
    logged = db.scalar(select(AuditLog).where(AuditLog.action == "admin.model.activate"))
    assert logged.details == {"name": "fund_ranker", "version": 1}
    assert (
        client.post("/api/admin/models/999999/activate", headers=admin_headers).status_code == 404
    )


def test_command_line_grants_and_revokes_admin(client, db, monkeypatch):
    login_headers(client, "owner@example.com")
    monkeypatch.setattr(admin_cli, "SessionLocal", lambda: nullcontext(db))
    assert admin_cli.set_role("Owner@Example.com", "admin") == "owner@example.com is now admin"
    assert admin_cli.set_role("owner@example.com", "admin") == "owner@example.com is already admin"
    assert (
        admin_cli.set_role("ghost@example.com", "admin")
        == "No account with e-mail ghost@example.com"
    )
    assert admin_cli.set_role("owner@example.com", "user") == "owner@example.com is now user"
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "cli.role.change")).all()
    assert [r.details["role"]["to"] for r in rows] == ["admin", "user"]
    assert all(r.actor_id is None for r in rows)
