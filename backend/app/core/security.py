"""Password hashing and JSON Web Token (JWT) helpers. No database or HTTP code here."""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

# Argon2id: memory-hard hashing algorithm, winner of the Password Hashing Competition.
# Each hash embeds its own random salt and parameters.
password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(user_id: int, role: str) -> str:
    """Signed token proving who the user is, valid for a limited time."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # subject: whom the token is about
        "role": role,
        "iat": now,  # issued at
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),  # expiry
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Return the token payload; raises jwt.InvalidTokenError if tampered with or expired."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
