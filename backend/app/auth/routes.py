import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.auth.email_service import send_password_reset_email
from app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.auth.security import (
    hash_password,
    verify_password,
    generate_opaque_token,
    hash_token,
)
from app.config import settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.models import User, UserProfile, Session as SessionModel, PasswordResetToken

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

GENERIC_LOGIN_ERROR = "Invalid email or password."
GENERIC_RESET_ERROR = "This reset link is invalid or has expired."


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.SESSION_TTL_HOURS * 3600,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")


def _create_session(db: DBSession, user: User) -> str:
    raw_token = generate_opaque_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(hours=settings.SESSION_TTL_HOURS),
    )
    db.add(session)
    db.commit()
    return raw_token


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
def register(request: Request, payload: RegisterRequest, response: Response, db: DBSession = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    # Every user gets an empty consumer profile up front (all fields optional,
    # filled in later via PATCH /users/me/profile). Never forces research fields.
    db.add(UserProfile(user_id=user.id))
    db.commit()
    db.refresh(user)

    raw_token = _create_session(db, user)
    _set_session_cookie(response, raw_token)

    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at)


@router.post("/login", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, payload: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Same generic error whether the email doesn't exist or the password is
    # wrong -- never reveal which one it was.
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    raw_token = _create_session(db, user)
    _set_session_cookie(response, raw_token)

    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DBSession = Depends(get_db)):
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if raw_token:
        token_hash = hash_token(raw_token)
        session = db.query(SessionModel).filter(SessionModel.token_hash == token_hash).first()
        if session and session.revoked_at is None:
            session.revoked_at = datetime.utcnow()
            db.commit()
    _clear_session_cookie(response)
    return None


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=current_user.created_at,
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_PASSWORD_RESET)
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: DBSession = Depends(get_db)):
    generic_response = {"detail": "If an account exists with that email, a password reset link has been sent."}

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active:
        # Always return the same response -- do not reveal whether the email exists.
        return generic_response

    raw_token = generate_opaque_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
    )
    db.add(reset_token)
    db.commit()

    reset_link = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password?token={raw_token}"
    send_password_reset_email(user.email, reset_link)

    return generic_response


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, db: DBSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at <= datetime.utcnow()
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_RESET_ERROR)

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=GENERIC_RESET_ERROR)

    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = datetime.utcnow()

    # Revoke every existing session -- a password reset should force
    # re-authentication everywhere, including on a device an attacker had
    # been using with a stolen session.
    db.query(SessionModel).filter(
        SessionModel.user_id == user.id, SessionModel.revoked_at.is_(None)
    ).update({SessionModel.revoked_at: datetime.utcnow()})

    db.commit()
    return {"detail": "Your password has been reset. Please log in again."}
