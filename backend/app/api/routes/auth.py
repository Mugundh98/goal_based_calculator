from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import Audit, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import Token, UserCreate, UserRead
from app.services.auth import EmailAlreadyRegisteredError, authenticate_user, register_user

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
