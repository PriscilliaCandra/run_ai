from typing import List
from pydantic import BaseModel, Field


class AIWorkoutItem(BaseModel):
    day: str
    workout_type: str
    distance_km: float
    pace_target: str
    intensity_zone: str
    warmup_cooldown: str = ""
    workout_execution: str = ""
    recovery_instruction: str = ""
    purpose: str = ""


class AIPersonalizedInsights(BaseModel):
    pacing_strategy: str = ""
    injury_prevention_note: str = ""
    nutrition_and_recovery_advice: str = ""


class AIWhyGenerated(BaseModel):
    key_influencing_factors: List[str] = Field(default_factory=list)
    ai_personalization_additions: str = ""


class AIPersonalizedPlan(BaseModel):
    """
    Schema for the AI-personalized plan, whether produced by a live LLM or the
    offline fallback synthesizer. Only textual/explanatory fields are expected to
    vary between runners; the numeric/structural fields are cross-checked against
    the deterministic rule-based baseline in app.ai.validator before this model
    is ever trusted.
    """
    coach_overview: str = ""
    weekly_mileage_km: float
    workouts: List[AIWorkoutItem]
    personalized_insights: AIPersonalizedInsights = Field(default_factory=AIPersonalizedInsights)
    ai_personalization_summary: List[str] = Field(default_factory=list)
    why_this_plan_was_generated: AIWhyGenerated = Field(default_factory=AIWhyGenerated)
