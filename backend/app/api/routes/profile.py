from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.profile import ProfileInput, ProfileRead
from app.services.profile import get_profile, upsert_profile
from app.services.retirement import resync_after_profile_change

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileRead)
def read_profile(user: CurrentUser, db: DbSession) -> ProfileRead:
    """The logged-in user's financial profile. 404 until it has been saved once."""
    profile = get_profile(db, user)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Financial profile not created yet")
    return ProfileRead.model_validate(profile)


@router.put("", response_model=ProfileRead)
def save_profile(data: ProfileInput, user: CurrentUser, db: DbSession) -> ProfileRead:
    """Create or replace the financial profile (idempotent)."""
    profile = upsert_profile(db, user, data)
    # A new date of birth moves the retirement year of the retirement goal.
    resync_after_profile_change(db, user)
    return ProfileRead.model_validate(profile)
