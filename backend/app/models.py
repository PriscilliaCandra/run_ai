import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Date, ForeignKey, Boolean, Index, UniqueConstraint
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
    workout_logs = relationship("WorkoutLog", back_populates="user", cascade="all, delete-orphan")


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

    # Consumer plan lifecycle (Phase 2). Both nullable: NULL for every
    # anonymous research plan, which never sets or reads these fields.
    # For a consumer plan: start_date = the day it was generated,
    # status one of 'active' | 'archived' (see app/routes/plan_routes.py --
    # only one 'active' consumer plan may exist per user at a time).
    start_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=True)

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
    scheduled_workouts = relationship("TrainingPlanWorkout", back_populates="training_plan", cascade="all, delete-orphan")


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


class TrainingPlanWorkout(Base):
    """
    A SCHEDULED/PLANNED workout day within a consumer training plan --
    distinct from WorkoutLog (an ACTUAL/completed workout). Read-only in
    Phase 2: a materialized snapshot of week 1 of the plan's generated JSON
    (rule_based_plan_json), taken once at plan-generation time.

    Only ever created for consumer plans (training_plans.user_id IS NOT
    NULL) -- anonymous research plans get zero rows here. Only week 1 is
    materialized because the rule engine (app/rules/generator.py) only
    produces full daily detail for week 1; weeks 2+ are intentionally not
    fabricated (see PHASE_2_DESIGN.md Section 3.2 / Section 6).
    """
    __tablename__ = "training_plan_workouts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    training_plan_id = Column(String(36), ForeignKey("training_plans.id"), nullable=False, index=True)
    week_number = Column(Integer, nullable=False)
    day_of_week = Column(String(10), nullable=False)  # "Monday".."Sunday"
    workout_type = Column(String(30), nullable=False)  # verbatim from the plan JSON, e.g. "Interval Training"
    distance_meters = Column(Integer, nullable=False)
    pace_target = Column(String(40), nullable=False)  # verbatim string, e.g. "05:15 - 05:30 /km"
    intensity_zone = Column(String(60), nullable=False)
    purpose = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    training_plan = relationship("TrainingPlan", back_populates="scheduled_workouts")
    workout_logs = relationship("WorkoutLog", back_populates="training_plan_workout")

    __table_args__ = (
        Index("ix_tpw_plan_week", "training_plan_id", "week_number"),
        UniqueConstraint("training_plan_id", "week_number", "day_of_week", name="uq_tpw_plan_week_day"),
    )


class WorkoutLog(Base):
    """
    An ACTUAL/completed workout logged by a consumer user -- distinct from
    TrainingPlanWorkout (a scheduled/planned day). Always user-owned;
    optionally linked to the TrainingPlanWorkout it was performed for
    (unused by any Phase 2 UI feature yet, but validated end-to-end now --
    see app/routes/workout_routes.py's cross-user-linking guard -- so
    Phase 3 needs no further schema/validation work to use it safely).
    """
    __tablename__ = "workout_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    workout_date = Column(Date, nullable=False)  # plain calendar date, no time-of-day, no timezone conversion

    # Stored as whole meters/seconds (not float km) to avoid floating-point
    # drift when summing many rows for weekly/monthly statistics. Pace is
    # NEVER stored -- always derived server-side from these two fields.
    distance_meters = Column(Integer, nullable=False)
    duration_seconds = Column(Integer, nullable=False)

    workout_type = Column(String(20), nullable=False)  # EASY | LONG_RUN | TEMPO | INTERVAL | RECOVERY | RACE | OTHER
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    cadence_spm = Column(Integer, nullable=True)
    elevation_gain_m = Column(Integer, nullable=True)
    rpe = Column(Integer, nullable=True)  # 1-10, Rate of Perceived Exertion
    notes = Column(Text, nullable=True)

    training_plan_workout_id = Column(String(36), ForeignKey("training_plan_workouts.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # soft delete -- rows are never physically removed

    user = relationship("User", back_populates="workout_logs")
    training_plan_workout = relationship("TrainingPlanWorkout", back_populates="workout_logs")

    __table_args__ = (
        Index("ix_workout_logs_user_date", "user_id", "workout_date"),
        Index("ix_workout_logs_user_deleted", "user_id", "deleted_at"),
    )
