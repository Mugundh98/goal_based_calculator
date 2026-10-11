"""API tests for registration, login and the current-user endpoint (real test database)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.deps import require_admin
from app.core.config import get_settings
from app.models.user import User

NEW_USER = {"email": "Asha@Example.com", "password": "secret123", "full_name": "Asha Rao"}


def register(client, **overrides):
    return client.post("/api/auth/register", json={**NEW_USER, **overrides})


def login(client, email="asha@example.com", password="secret123"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Registration ---------------------------------------------------------------------------


def test_register_creates_user(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "asha@example.com"  # normalised to lower case
    assert body["full_name"] == "Asha Rao"
    assert body["role"] == "user"
    assert "password" not in body and "password_hash" not in body


def test_password_is_stored_hashed(client, db):
    register(client)
    user = db.scalar(select(User).where(User.email == "asha@example.com"))
    assert user.password_hash != "secret123"
    assert user.password_hash.startswith("$argon2id$")


def test_duplicate_email_is_rejected_case_insensitively(client):
    register(client)
    response = register(client, email="ASHA@example.com")
    assert response.status_code == 409


@pytest.mark.parametrize(
    "field, value",
    [
        ("email", "not-an-email"),
        ("password", "short1"),  # under 8 characters
        ("password", "onlyletters"),  # no digit
        ("full_name", "A"),
    ],
)
def test_invalid_registration_input_is_rejected(client, field, value):
    assert register(client, **{field: value}).status_code == 422


# --- Login ----------------------------------------------------------------------------------


def test_login_returns_bearer_token(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert body["access_token"].count(".") == 2  # header.payload.signature


def test_login_email_is_case_insensitive(client):
    register(client)
    assert login(client, email="ASHA@EXAMPLE.COM").status_code == 200


def test_wrong_password_and_unknown_email_give_same_error(client):
    register(client)
    wrong_password = login(client, password="wrong123")
    unknown_email = login(client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_inactive_user_cannot_log_in(client, db):
    register(client)
    user = db.scalar(select(User).where(User.email == "asha@example.com"))
    user.is_active = False
    db.commit()
    assert login(client).status_code == 401


# --- Current user ---------------------------------------------------------------------------


def test_me_returns_logged_in_user(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["email"] == "asha@example.com"


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_invalid_token(client):
    assert client.get("/api/auth/me", headers=auth_header("abc.def.ghi")).status_code == 401


def test_me_rejects_expired_token(client):
    user_id = register(client).json()["id"]
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode(
        {"sub": str(user_id), "role": "user", "iat": past, "exp": past},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/api/auth/me", headers=auth_header(expired)).status_code == 401


def test_token_for_deleted_user_is_rejected(client, db):
    register(client)
    token = login(client).json()["access_token"]
    db.delete(db.scalar(select(User).where(User.email == "asha@example.com")))
    db.commit()
    assert client.get("/api/auth/me", headers=auth_header(token)).status_code == 401


# --- Roles ----------------------------------------------------------------------------------


def test_require_admin_blocks_normal_user():
    with pytest.raises(HTTPException) as error:
        require_admin(User(role="user"))
    assert error.value.status_code == 403


def test_require_admin_allows_admin():
    admin = User(role="admin")
    assert require_admin(admin) is admin
