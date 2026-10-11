"""Unit tests for password hashing and JWT helpers (no database)."""

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_plain_text_and_verifies():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert hashed.startswith("$argon2id$")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong123", hashed)


def test_same_password_gives_different_hashes():
    # A random salt is generated for every hash.
    assert hash_password("secret123") != hash_password("secret123")


def test_token_round_trip():
    payload = decode_access_token(create_access_token(user_id=42, role="user"))
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
    assert payload["exp"] > payload["iat"]


def test_tampered_token_is_rejected():
    # A user edits their own token to claim the admin role but keeps the old signature.
    token = create_access_token(user_id=42, role="user")
    header, body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=="))
    payload["role"] = "admin"
    forged_body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(f"{header}.{forged_body}.{signature}")


def test_token_signed_with_other_key_is_rejected():
    forged = jwt.encode(
        {"sub": "1", "role": "admin"},
        "attacker-key-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)


def test_expired_token_is_rejected():
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=5)
    expired = jwt.encode(
        {"sub": "1", "role": "user", "iat": past, "exp": past},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)
