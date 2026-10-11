"""Financial profile: one per user, created or replaced with PUT."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import FinancialProfile
from app.models.user import User
from app.schemas.profile import ProfileInput


def get_profile(db: Session, user: User) -> FinancialProfile | None:
    return db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user.id))


def upsert_profile(db: Session, user: User, data: ProfileInput) -> FinancialProfile:
    profile = get_profile(db, user)
    if profile is None:
        profile = FinancialProfile(user_id=user.id)
        db.add(profile)
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
