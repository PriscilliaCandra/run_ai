"""
FastAPI dependencies that resolve the authenticated user from the session
cookie. These are the ONLY places "who is the current user" is determined --
every ownership check downstream relies on this, never on anything the
client sends in a request body.
"""
from datetime import datetime
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.security import hash_token
from app.config import settings
from app.database import get_db
from app.models import Session as SessionModel, User


def _resolve_user_from_token(raw_token: Optional[str], db: DBSession) -> Optional[User]:
    if not raw_token:
        return None

    token_hash = hash_token(raw_token)
    session = (
        db.query(SessionModel)
        .filter(SessionModel.token_hash == token_hash)
        .first()
    )
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if session.expires_at <= datetime.utcnow():
        return None

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None or not user.is_active:
        return None
    return user


def get_optional_current_user(
    db: DBSession = Depends(get_db),
    session_token: Optional[str] = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
) -> Optional[User]:
    """Returns the authenticated user if a valid session cookie is present, else None.
    Used by endpoints that support BOTH anonymous (research) and authenticated
    (consumer) access, such as plan generation."""
    return _resolve_user_from_token(session_token, db)


def get_current_user(
    user: Optional[User] = Depends(get_optional_current_user),
) -> User:
    """Requires a valid, non-expired, non-revoked session. Raises 401 otherwise."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user
