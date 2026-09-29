from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import UserProfileUpsert, UserProfileResponse
from app.database import get_db
from app.models import User, UserProfile

router = APIRouter(prefix="/users/me", tags=["User Profile"])


@router.get("/profile", response_model=UserProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if profile is None:
        # Defensive: registration always creates one, but don't 500 if it's ever missing.
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.patch("/profile", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpsert,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).first()
    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    # Only overwrite fields the client actually sent, so a partial PATCH
    # never blanks out fields the user didn't intend to touch.
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile
