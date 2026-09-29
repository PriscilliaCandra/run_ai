"""
Rate limiting for public-facing and expensive operations (login, register,
password reset, and plan generation -- which can invoke a paid LLM API).

Kept deliberately simple per the Phase 1 scope: an in-memory, single-process
limiter (slowapi/limits) is enough for an MVP-scale deployment. All limits
are configurable via environment variables (app/config.py /
.env.example) rather than hardcoded, so they can be tuned without a code
change. Move to a shared backend (e.g. Redis) only if/when the API runs as
multiple processes/instances behind a load balancer.
"""
from typing import Optional

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.security import hash_token
from app.config import settings
from app.database import SessionLocal
from app.models import Session as SessionModel, User
from datetime import datetime


def _current_user_or_ip_key(request: Request) -> str:
    """
    Rate-limits authenticated users by their user id (so one account can't
    exhaust a shared IP's quota for everyone behind it, e.g. NAT/office wifi)
    and falls back to per-IP for anonymous/research requests.
    """
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if raw_token:
        db = SessionLocal()
        try:
            token_hash = hash_token(raw_token)
            session = db.query(SessionModel).filter(SessionModel.token_hash == token_hash).first()
            if (
                session is not None
                and session.revoked_at is None
                and session.expires_at > datetime.utcnow()
            ):
                user = db.query(User).filter(User.id == session.user_id).first()
                if user is not None and user.is_active:
                    return f"user:{user.id}"
        finally:
            db.close()
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_remote_address)
