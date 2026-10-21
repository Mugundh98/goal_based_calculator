"""Registration, login and the account: password changes and resets by security question."""

import hashlib
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.auth import SECURITY_QUESTIONS, UserCreate

RESET_ATTEMPTS = 5  # wrong answers for one address...
RESET_WINDOW = timedelta(hours=1)  # ...within this time lock its resets until the window passes


class EmailAlreadyRegisteredError(Exception):
    pass


class ResetLockedError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def normalise_answer(answer: str) -> str:
    """'  Delhi Public  School ' and 'delhi public school' are the same answer."""
    return " ".join(answer.casefold().split())


def _set_question(user: User, question: str, answer: str) -> None:
    user.security_question = question
    user.security_answer_hash = hash_password(normalise_answer(answer))


def register_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, data.email):
        raise EmailAlreadyRegisteredError(data.email)
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
    )
    if data.security_question and data.security_answer:
        _set_question(user, data.security_question, data.security_answer)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user if the credentials are valid, otherwise None."""
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# --- The account page -----------------------------------------------------------------------


def update_name(db: Session, user: User, full_name: str) -> User:
    user.full_name = full_name
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, current: str, new: str) -> bool:
    """False (and no change) when the current password is wrong."""
    if not verify_password(current, user.password_hash):
        return False
    user.password_hash = hash_password(new)
    db.commit()
    return True


def set_security_question(
    db: Session, user: User, current: str, question: str, answer: str
) -> bool:
    """False (and no change) when the current password is wrong."""
    if not verify_password(current, user.password_hash):
        return False
    _set_question(user, question, answer)
    db.commit()
    db.refresh(user)
    return True


# --- Forgot password ------------------------------------------------------------------------


def _decoy_question(email: str) -> str:
    """The same made-up question every time for an address without one, so this step cannot be
    used to find out which addresses have an account."""
    digest = hashlib.sha256(email.encode()).digest()
    return SECURITY_QUESTIONS[digest[0] % len(SECURITY_QUESTIONS)]


def reset_question(db: Session, email: str) -> str:
    user = get_user_by_email(db, email)
    if user is not None and user.is_active and user.security_question:
        return user.security_question
    return _decoy_question(email.lower())


def recent_failures(db: Session, email: str, now: datetime | None = None) -> int:
    since = (now or datetime.now(UTC)) - RESET_WINDOW
    return (
        db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "auth.password_reset_failed",
                AuditLog.actor_email == email.lower(),
                AuditLog.created_at >= since,
            )
        )
        or 0
    )


@lru_cache
def _dummy_hash() -> str:
    return hash_password("no such answer")


def reset_password(db: Session, email: str, answer: str, new_password: str) -> User | None:
    """Set a new password if the answer matches; None if it does not (the caller records the
    failure). ResetLockedError after RESET_ATTEMPTS wrong answers within RESET_WINDOW."""
    if recent_failures(db, email) >= RESET_ATTEMPTS:
        raise ResetLockedError(email)
    user = get_user_by_email(db, email)
    stored = user.security_answer_hash if user is not None and user.is_active else None
    # A hash is checked even without an account, so a reply takes the same time either way.
    matches = verify_password(normalise_answer(answer), stored or _dummy_hash())
    if user is None or stored is None or not matches:
        return None
    user.password_hash = hash_password(new_password)
    db.commit()
    return user
