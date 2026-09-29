import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.ai.schemas import AIPersonalizedPlan

def parse_time_to_seconds(time_str: str) -> int:
    """Converts MM:SS or HH:MM:SS string to total seconds."""
    time_str = time_str.strip()
    parts = time_str.split(":")
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid time format '{time_str}'. Expected MM:SS or HH:MM:SS.")

def format_seconds_to_pace(seconds: int) -> str:
    """Converts seconds into MM:SS format."""
    minutes = seconds // 60
    rem_seconds = seconds % 60
    return f"{minutes:02d}:{rem_seconds:02d}"

class RunnerProfileCreate(BaseModel):
    age: int = Field(..., ge=12, le=99, description="Runner's age")
    gender: str = Field(..., description="Gender (Male, Female, Other)")
    experience_level: str = Field(..., description="Beginner, Intermediate, or Advanced")
    pb_5k: str = Field(..., description="Current 5K Personal Best in MM:SS (e.g. 24:56)")
    pb_10k: Optional[str] = Field(None, description="Optional 10K Personal Best in MM:SS (e.g. 52:10)")
    target_race_distance: str = Field(..., description="Target race: 5K, 10K, or Half Marathon")
    target_race_time: str = Field(..., description="Target race time (e.g. 23:00 or 01:45:00)")
    current_weekly_mileage: float = Field(..., gt=0, le=200, description="Current weekly mileage in km")
    training_days_per_week: int = Field(..., ge=1, le=7, description="Available training days per week (1-7)")
    preferred_training_days: List[str] = Field(..., min_length=1, description="List of preferred training days")
    plan_duration_weeks: int = Field(..., ge=4, le=24, description="Training duration in weeks (4-24)")
    injury_limitations: Optional[str] = Field(None, description="Any past or current injury or limitations")
    easy_run_pace: str = Field(..., description="Current average easy-run pace in MM:SS /km (e.g. 05:45)")

    @field_validator("pb_5k", "pb_10k", "easy_run_pace")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        pattern = r"^\d{1,2}:\d{2}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Time must be formatted as MM:SS (e.g. 24:56 or 05:45)")
        parse_time_to_seconds(v)
        return v.strip()

    @field_validator("target_race_time")
    @classmethod
    def validate_target_time(cls, v: str) -> str:
        pattern = r"^(\d{1,2}:)?\d{1,2}:\d{2}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Target time must be formatted as MM:SS or HH:MM:SS (e.g. 23:00 or 01:45:00)")
        parse_time_to_seconds(v)
        return v.strip()

    @field_validator("target_race_distance")
    @classmethod
    def validate_race_distance(cls, v: str) -> str:
        valid_distances = ["5K", "10K", "Half Marathon"]
        matched = [d for d in valid_distances if d.lower() == v.strip().lower()]
        if not matched:
            raise ValueError(f"Target race distance must be one of: {', '.join(valid_distances)}")
        return matched[0]


class WorkoutItem(BaseModel):
    day: str
    workout_type: str  # Easy Run, Tempo Run, Interval Training, Long Run, Rest / Recovery
    distance_km: float
    pace_target: str   # e.g. "05:15 - 05:30 /km"
    intensity_zone: str # e.g. "Zone 2 (Aerobic)", "Zone 4 (Threshold)"
    recovery_instruction: str
    purpose: str

class WeeklyPlan(BaseModel):
    week_number: int
    weekly_mileage_km: float
    focus: str
    workouts: List[WorkoutItem]

class PlanGenerationResponse(BaseModel):
    plan_id: str
    runner_profile_id: str
    calculated_vdot: float
    target_pace_per_km: str
    rule_based_plan: Dict[str, Any]
    ai_personalized_plan: AIPersonalizedPlan
    explainability: Dict[str, Any]
    ai_model_used: str
    created_at: datetime
    # Phase 3 additive field: None for every anonymous research plan (which
    # never sets a status at all -- see TrainingPlan.status); 'active' or
    # 'archived' for a consumer plan. Lets the consumer frontend avoid
    # offering a "log this workout" action that the backend would reject
    # for an archived plan's schedule (Section 7's locked decision).
    status: Optional[str] = None

class PlanEvaluationCreate(BaseModel):
    training_plan_id: str
    evaluated_plan_type: str = Field("ai_personalized", description="'rule_based' or 'ai_personalized'")
    personalization_score: int = Field(..., ge=1, le=5, description="1 to 5 score for Personalization")
    usefulness_score: int = Field(..., ge=1, le=5, description="1 to 5 score for Usefulness")
    clarity_score: int = Field(..., ge=1, le=5, description="1 to 5 score for Clarity")
    confidence_score: int = Field(..., ge=1, le=5, description="1 to 5 score for Confidence in following plan")
    comments: Optional[str] = None

    @field_validator("evaluated_plan_type")
    @classmethod
    def validate_plan_type(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in ["rule_based", "ai_personalized"]:
            raise ValueError("evaluated_plan_type must be either 'rule_based' or 'ai_personalized'")
        return clean

class PlanEvaluationResponse(BaseModel):
    id: str
    training_plan_id: str
    evaluated_plan_type: str
    personalization_score: int
    usefulness_score: int
    clarity_score: int
    confidence_score: int
    comments: Optional[str]
    created_at: datetime

class DimensionStats(BaseModel):
    """
    Descriptive statistics for a single Likert dimension within one evaluation
    group. median/std_dev are null when there isn't enough data to compute
    them meaningfully (median needs N>=1, std_dev needs N>=2) rather than
    reporting a misleading number like std_dev=0.0 for a single observation.
    """
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None

class EvaluationCategoryStats(BaseModel):
    count: int
    personalization: DimensionStats
    usefulness: DimensionStats
    clarity: DimensionStats
    confidence: DimensionStats
    overall_mean: Optional[float] = None

class EvaluationStatsResponse(BaseModel):
    """
    Rule-Based Baseline and AI-Personalized Plan statistics are always reported
    as two separate EvaluationCategoryStats groups. This response intentionally
    has no top-level combined/blended score across the two groups -- comparing
    them is left to the researcher, not computed as a "winner" by the API.
    """
    total_evaluations: int
    rule_based_stats: EvaluationCategoryStats
    ai_personalized_stats: EvaluationCategoryStats
    recent_comments: List[Dict[str, Any]]
