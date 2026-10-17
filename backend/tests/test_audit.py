"""The audit log: what is recorded, and that nobody can rewrite it."""

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import AuditLog, User
from app.services import audit
from tests.conftest import login_headers

THIS_YEAR = date.today().year


def actions(db):
    return [(e.action, e.actor_email) for e in db.scalars(select(AuditLog).order_by(AuditLog.id))]


def test_unknown_actions_are_rejected(db):
    with pytest.raises(ValueError, match="Unknown audit action"):
        audit.record(db, "goal.creat")


def test_audit_rows_cannot_be_changed_or_deleted(db):
    entry = audit.record(db, "auth.login", actor_email="someone@example.com")
    db.commit()
    for statement in (
        "UPDATE audit_log SET actor_email = 'hacker@example.com'",
        "DELETE FROM audit_log",
    ):
        savepoint = db.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text(statement))
        savepoint.rollback()
    db.expire_all()
    assert db.get(AuditLog, entry.id).actor_email == "someone@example.com"


def test_sign_up_logins_and_failures_are_recorded(client, db):
    headers = login_headers(client, "user@example.com")
    client.post("/api/auth/login", data={"username": "USER@example.com ", "password": "wrong"})
    assert actions(db) == [
        ("auth.register", "user@example.com"),
        ("auth.login", "user@example.com"),
        ("auth.login_failed", "user@example.com"),  # normalised like a real login
    ]
    last = db.scalars(select(AuditLog).order_by(AuditLog.id.desc())).first()
    assert last.actor_id is None and last.ip_address == "testclient"
    assert headers


def test_goal_changes_are_recorded_with_what_changed(client, db, auth_headers):
    body = {"goal_type": "car", "name": "Car", "target_amount": 800_000,
            "target_year": THIS_YEAR + 3}  # fmt: skip
    goal_id = client.post("/api/goals", json=body, headers=auth_headers).json()["id"]
    client.put(f"/api/goals/{goal_id}", json=body | {"name": "New car"}, headers=auth_headers)
    client.delete(f"/api/goals/{goal_id}", headers=auth_headers)
    rows = db.scalars(select(AuditLog).where(AuditLog.action.startswith("goal."))
                      .order_by(AuditLog.id)).all()  # fmt: skip
    assert [(r.action, r.entity_id, r.details["name"]) for r in rows] == [
        ("goal.create", goal_id, "Car"),
        ("goal.update", goal_id, "New car"),
        ("goal.delete", goal_id, "New car"),
    ]
    assert {r.actor_email for r in rows} == {"user@example.com"}


def test_failed_actions_are_not_recorded(client, db, auth_headers):
    client.post("/api/goals", json={"name": ""}, headers=auth_headers)  # 422
    client.delete("/api/goals/999999", headers=auth_headers)  # 404
    assert not [a for a, _ in actions(db) if a.startswith("goal.")]


def test_entries_filter_by_action_prefix_and_actor(db):
    alice, bob = (User(email=f"{n}@example.com", password_hash="x", full_name=n) for n in "ab")
    db.add_all([alice, bob])
    db.flush()
    for action, actor in (("goal.create", alice), ("goal.delete", alice), ("auth.login", bob)):
        audit.record(db, action, actor=actor)
    db.commit()
    assert audit.entries(db, action="goal.").total == 2
    assert audit.entries(db, action="goal.create").total == 1
    assert [e.action for e in audit.entries(db, actor_id=bob.id).items] == ["auth.login"]
    assert [e.action for e in audit.entries(db, page_size=1).items] == ["auth.login"]  # newest
    assert audit.last_logins(db, [alice.id, bob.id]).keys() == {bob.id}
