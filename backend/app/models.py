import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    """
    Consumer account identity. Deliberately separate from RunnerProfile:
    RunnerProfile is anonymous research-submission data with no link to a
    user; User is the auth/account identity for the consumer product.
    """
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    training_plans = relationship("TrainingPlan", back_populates="user")


class UserProfile(Base):
    """
    Consumer-facing running profile, separate from the auth identity (User)
    and separate from the anonymous research RunnerProfile. Only the fields
    actually needed to personalize a plan -- no unnecessary PII.
    """
    __tablename__ = "user_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True)

    age = Column(Integer, nullable=True)
    experience_level = Column(String(30), nullable=True)
    pb_5k = Column(String(10), nullable=True)
    pb_10k = Column(String(10), nullable=True)
    target_race_distance = Column(String(30), nullable=True)
    target_race_time = Column(String(10), nullable=True)
    current_weekly_mileage = Column(Float, nullable=True)
    training_days_per_week = Column(Integer, nullable=True)
    injury_limitations = Column(Text, nullable=True)
    easy_run_pace = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


class Session(Base):
    """
    Server-side session record backing the httpOnly session cookie.
    Only a SHA-256 hash of the session token is ever stored -- never the
    raw token, which exists only in the client's cookie.
    """
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")


class PasswordResetToken(Base):
    """Single-use, short-lived, hashed password reset token."""
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="reset_tokens")

class RunnerProfile(Base):
    __tablename__ = "runner_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    experience_level = Column(String(30), nullable=False)
    pb_5k = Column(String(10), nullable=False)
    pb_10k = Column(String(10), nullable=True)
    target_race_distance = Column(String(30), nullable=False)
    target_race_time = Column(String(10), nullable=False)
    current_weekly_mileage = Column(Float, nullable=False)
    training_days_per_week = Column(Integer, nullable=False)
    preferred_training_days = Column(String(100), nullable=False)  # Comma separated, e.g. "Tuesday,Thursday,Saturday,Sunday"
    plan_duration_weeks = Column(Integer, nullable=False)
    injury_limitations = Column(Text, nullable=True)
    easy_run_pace = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    training_plans = relationship("TrainingPlan", back_populates="profile", cascade="all, delete-orphan")


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    runner_profile_id = Column(String(36), ForeignKey("runner_profiles.id"), nullable=False)

    # Nullable by design: NULL means an anonymous research-generated plan
    # (the existing, unchanged behavior). Only set when the request that
    # generated the plan carried a valid, authenticated session -- a plan
    # is never attached to a user after the fact, and a client can never
    # set this value itself.
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    calculated_vdot = Column(Float, nullable=False)
    target_pace = Column(String(10), nullable=False)

    # Store JSON strings for rule-based and AI-generated outputs for direct research comparison
    rule_based_plan_json = Column(Text, nullable=False)
    ai_plan_json = Column(Text, nullable=False)

    explainability_summary = Column(Text, nullable=False)
    ai_model_used = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("RunnerProfile", back_populates="training_plans")
    evaluations = relationship("PlanEvaluation", back_populates="plan", cascade="all, delete-orphan")
    user = relationship("User", back_populates="training_plans")


class PlanEvaluation(Base):
    __tablename__ = "plan_evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    training_plan_id = Column(String(36), ForeignKey("training_plans.id"), nullable=False)
    
    # Identifies whether the participant evaluated the 'rule_based' baseline or the 'ai_personalized' plan
    evaluated_plan_type = Column(String(20), nullable=False, default="ai_personalized")
    
    # 1 to 5 Likert Scale criteria for S2 research paper
    personalization_score = Column(Integer, nullable=False)
    usefulness_score = Column(Integer, nullable=False)
    clarity_score = Column(Integer, nullable=False)
    confidence_score = Column(Integer, nullable=False)
    
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("TrainingPlan", back_populates="evaluations")
