from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import Audit, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import (
    SECURITY_QUESTIONS,
    ForgotPasswordQuestion,
    ForgotPasswordStart,
    NameUpdate,
    PasswordChange,
    PasswordReset,
    SecurityQuestionSet,
    Token,
    UserCreate,
    UserRead,
)
from app.services import auth as service
from app.services.auth import EmailAlreadyRegisteredError, authenticate_user, register_user

WRONG_PASSWORD = "Your current password is not correct"

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: DbSession, audit: Audit) -> UserRead:
    """Create a new account."""
    try:
        user = register_user(db, data)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        ) from None
    audit("auth.register", user, entity_type="user", entity_id=user.id)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession, audit: Audit
) -> Token:
    """OAuth2 password flow: form fields `username` (the email) and `password`."""
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        # Logged: repeated failures for one account or address point to password guessing.
        audit("auth.login_failed", actor_email=form.username.strip().lower()[:255])
        # Same message for unknown email and wrong password, so emails cannot be probed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    audit("auth.login", user)
    settings = get_settings()
    return Token(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    """The currently logged-in user."""
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
def update_me(data: NameUpdate, user: CurrentUser, db: DbSession, audit: Audit) -> UserRead:
    """Change the name shown in the app (the e-mail is the login and cannot change)."""
    service.update_name(db, user, data.full_name)
    audit("auth.name.change", user, entity_type="user", entity_id=user.id)
    return UserRead.model_validate(user)


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChange, user: CurrentUser, db: DbSession, audit: Audit) -> None:
    """Change the password; the current one is asked again."""
    if not service.change_password(db, user, data.current_password, data.new_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=WRONG_PASSWORD)
    audit("auth.password.change", user, entity_type="user", entity_id=user.id)


@router.get("/security-questions", response_model=list[str])
def security_questions() -> list[str]:
    """The questions to choose from for "forgot password"."""
    return list(SECURITY_QUESTIONS)


@router.put("/security-question", response_model=UserRead)
def set_security_question(
    data: SecurityQuestionSet, user: CurrentUser, db: DbSession, audit: Audit
) -> UserRead:
    """Set or change the security question; the current password is asked again."""
    if not service.set_security_question(
        db, user, data.current_password, data.question, data.answer
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=WRONG_PASSWORD)
    audit("auth.security_question.set", user, entity_type="user", entity_id=user.id)
    return UserRead.model_validate(user)


@router.post("/forgot-password/question", response_model=ForgotPasswordQuestion)
def forgot_password_question(data: ForgotPasswordStart, db: DbSession) -> ForgotPasswordQuestion:
    """Step 1: the security question for an e-mail address (a stand-in one for an address
    without an account or a question, so accounts cannot be discovered this way)."""
    return ForgotPasswordQuestion(question=service.reset_question(db, data.email))


@router.post("/forgot-password/reset", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password_reset(data: PasswordReset, db: DbSession, audit: Audit) -> None:
    """Step 2: a new password, if the answer matches. Five wrong answers in an hour lock resets
    for that address for the rest of the hour."""
    try:
        user = service.reset_password(db, data.email, data.answer, data.new_password)
    except service.ResetLockedError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many wrong answers. Try again in an hour, or ask the administrator.",
        ) from None
    if user is None:
        audit("auth.password_reset_failed", actor_email=data.email[:255])
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "That answer does not match. Answers ignore capitals and extra spaces. If you "
                "never set a security question, ask the administrator to reset your password."
            ),
        )
    audit("auth.password_reset", user, entity_type="user", entity_id=user.id)
