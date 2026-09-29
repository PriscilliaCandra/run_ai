import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.security import normalize_email


def _validate_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("Password must contain at least one letter.")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one number.")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., description="At least 8 characters, with at least one letter and one number.")
    display_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Display name cannot be empty.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize(cls, v: str) -> str:
        return normalize_email(v)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: datetime


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize(cls, v: str) -> str:
        return normalize_email(v)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserProfileUpsert(BaseModel):
    """All fields optional: a consumer profile can be filled in incrementally."""
    age: Optional[int] = Field(None, ge=12, le=99)
    experience_level: Optional[str] = None
    pb_5k: Optional[str] = None
    pb_10k: Optional[str] = None
    target_race_distance: Optional[str] = None
    target_race_time: Optional[str] = None
    current_weekly_mileage: Optional[float] = Field(None, gt=0, le=200)
    training_days_per_week: Optional[int] = Field(None, ge=1, le=7)
    injury_limitations: Optional[str] = None
    easy_run_pace: Optional[str] = None

    @field_validator("pb_5k", "pb_10k", "easy_run_pace")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        pattern = r"^\d{1,2}:\d{2}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Time must be formatted as MM:SS (e.g. 24:56 or 05:45)")
        return v.strip()


class UserProfileResponse(BaseModel):
    age: Optional[int]
    experience_level: Optional[str]
    pb_5k: Optional[str]
    pb_10k: Optional[str]
    target_race_distance: Optional[str]
    target_race_time: Optional[str]
    current_weekly_mileage: Optional[float]
    training_days_per_week: Optional[int]
    injury_limitations: Optional[str]
    easy_run_pace: Optional[str]
    updated_at: Optional[datetime]
