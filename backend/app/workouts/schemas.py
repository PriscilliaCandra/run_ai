from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import format_seconds_to_pace


class WorkoutType(str, Enum):
    EASY = "EASY"
    LONG_RUN = "LONG_RUN"
    TEMPO = "TEMPO"
    INTERVAL = "INTERVAL"
    RECOVERY = "RECOVERY"
    RACE = "RACE"
    OTHER = "OTHER"


def _pace_display(distance_meters: int, duration_seconds: int) -> tuple:
    """Returns (pace_sec_per_km, pace_display). Pace is ALWAYS derived here --
    never accepted or stored as a user-entered value."""
    if distance_meters <= 0:
        return None, "N/A"
    pace_sec_per_km = round(duration_seconds / (distance_meters / 1000.0))
    return pace_sec_per_km, f"{format_seconds_to_pace(pace_sec_per_km)} /km"


class WorkoutLogCreate(BaseModel):
    workout_date: date
    distance_meters: int = Field(..., gt=0, le=300_000)
    duration_seconds: int = Field(..., ge=60, le=172_800)
    workout_type: WorkoutType
    avg_heart_rate: Optional[int] = Field(None, ge=30, le=250)
    max_heart_rate: Optional[int] = Field(None, ge=30, le=250)
    cadence_spm: Optional[int] = Field(None, ge=100, le=250)
    elevation_gain_m: Optional[int] = Field(None, ge=0, le=10_000)
    rpe: Optional[int] = Field(None, ge=1, le=10)
    notes: Optional[str] = Field(None, max_length=2000)
    # If supplied, ownership through training_plan_workout -> training_plan
    # -> training_plan.user_id is verified in the route handler (never
    # trusted from the client as authority) -- see
    # app/routes/workout_routes.py::_resolve_owned_training_plan_workout.
    training_plan_workout_id: Optional[str] = None

    @field_validator("workout_date")
    @classmethod
    def not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Workout date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def check_heart_rate_order(self):
        if self.avg_heart_rate is not None and self.max_heart_rate is not None:
            if self.avg_heart_rate > self.max_heart_rate:
                raise ValueError("Average heart rate cannot exceed max heart rate.")
        return self


class WorkoutLogUpdate(BaseModel):
    """All fields optional -- a partial PATCH only touches fields explicitly
    sent (exclude_unset semantics in the route handler, same pattern as
    UserProfileUpsert in Phase 1). Heart-rate-order and future-date checks
    are re-validated in the route against the MERGED (existing + incoming)
    values, since a partial update might only touch one of the two HR
    fields or leave the date untouched."""
    workout_date: Optional[date] = None
    distance_meters: Optional[int] = Field(None, gt=0, le=300_000)
    duration_seconds: Optional[int] = Field(None, ge=60, le=172_800)
    workout_type: Optional[WorkoutType] = None
    avg_heart_rate: Optional[int] = Field(None, ge=30, le=250)
    max_heart_rate: Optional[int] = Field(None, ge=30, le=250)
    cadence_spm: Optional[int] = Field(None, ge=100, le=250)
    elevation_gain_m: Optional[int] = Field(None, ge=0, le=10_000)
    rpe: Optional[int] = Field(None, ge=1, le=10)
    notes: Optional[str] = Field(None, max_length=2000)
    training_plan_workout_id: Optional[str] = None

    @field_validator("workout_date")
    @classmethod
    def not_in_future(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("Workout date cannot be in the future.")
        return v


class WorkoutLogResponse(BaseModel):
    id: str
    workout_date: date
    distance_meters: int
    distance_km: float
    duration_seconds: int
    pace_sec_per_km: Optional[int]
    pace_display: str
    workout_type: str
    avg_heart_rate: Optional[int]
    max_heart_rate: Optional[int]
    cadence_spm: Optional[int]
    elevation_gain_m: Optional[int]
    rpe: Optional[int]
    notes: Optional[str]
    training_plan_workout_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, wl) -> "WorkoutLogResponse":
        pace_sec, pace_disp = _pace_display(wl.distance_meters, wl.duration_seconds)
        return cls(
            id=wl.id,
            workout_date=wl.workout_date,
            distance_meters=wl.distance_meters,
            distance_km=round(wl.distance_meters / 1000.0, 2),
            duration_seconds=wl.duration_seconds,
            pace_sec_per_km=pace_sec,
            pace_display=pace_disp,
            workout_type=wl.workout_type,
            avg_heart_rate=wl.avg_heart_rate,
            max_heart_rate=wl.max_heart_rate,
            cadence_spm=wl.cadence_spm,
            elevation_gain_m=wl.elevation_gain_m,
            rpe=wl.rpe,
            notes=wl.notes,
            training_plan_workout_id=wl.training_plan_workout_id,
            created_at=wl.created_at,
            updated_at=wl.updated_at,
        )


class WorkoutLogListResponse(BaseModel):
    items: List[WorkoutLogResponse]
    total: int
    page: int
    page_size: int


class TrainingPlanWorkoutResponse(BaseModel):
    id: str
    week_number: int
    day_of_week: str
    workout_type: str
    distance_meters: int
    distance_km: float
    pace_target: str
    intensity_zone: str
    purpose: str

    @classmethod
    def from_model(cls, tpw) -> "TrainingPlanWorkoutResponse":
        return cls(
            id=tpw.id,
            week_number=tpw.week_number,
            day_of_week=tpw.day_of_week,
            workout_type=tpw.workout_type,
            distance_meters=tpw.distance_meters,
            distance_km=round(tpw.distance_meters / 1000.0, 2),
            pace_target=tpw.pace_target,
            intensity_zone=tpw.intensity_zone,
            purpose=tpw.purpose,
        )


class PeriodTotals(BaseModel):
    """Descriptive statistics only -- no score, ranking, or prediction of any kind."""
    total_distance_km: float
    run_count: int
    total_duration_seconds: int
    average_pace_display: Optional[str]  # volume-weighted (total_duration / total_distance); null when run_count == 0


class ActivePlanSummary(BaseModel):
    plan_id: str
    target_race_distance: str
    target_pace_per_km: str
    current_week: int
    total_weeks: int
    today_scheduled_workout: Optional[TrainingPlanWorkoutResponse]
    week1_detail_available: bool  # false => detailed daily workouts aren't materialized past week 1 (see PHASE_2_DESIGN.md Section 9.3)


class DashboardSummaryResponse(BaseModel):
    display_name: str
    active_plan: Optional[ActivePlanSummary]
    this_week: PeriodTotals
    this_month: PeriodTotals
    recent_activities: List[WorkoutLogResponse]
    has_any_workout_history: bool
