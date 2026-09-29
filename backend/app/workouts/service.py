"""
Consumer plan lifecycle helpers, used only from the authenticated branch of
plan generation (app/routes/plan_routes.py). Never called for anonymous
research plan generation -- research plans never get a status/start_date
or any training_plan_workouts rows.
"""
from typing import Any, Dict

from sqlalchemy.orm import Session as DBSession

from app.models import TrainingPlan, TrainingPlanWorkout


def archive_previous_active_plans(db: DBSession, user_id: str) -> None:
    """Only one consumer training plan may be 'active' per user at a time.
    Called before activating a newly generated plan. Scoped strictly to
    this user's own rows -- never touches another user's plans, and never
    matches an anonymous research plan (user_id IS NULL is never selected
    by this equality filter)."""
    db.query(TrainingPlan).filter(
        TrainingPlan.user_id == user_id,
        TrainingPlan.status == "active",
    ).update({TrainingPlan.status: "archived"})


def materialize_week_one(db: DBSession, training_plan_id: str, rule_plan: Dict[str, Any]) -> None:
    """
    Creates exactly 7 TrainingPlanWorkout rows (one per calendar day, Monday
    through Sunday, including rest days) from week 1 of the deterministic
    rule-based plan JSON. Only ever called for a consumer (user-owned) plan
    -- see PHASE_2_DESIGN.md Section 3.2 for why only week 1 is materialized
    (the rule engine does not produce daily detail for weeks 2+).
    """
    for w in rule_plan["week_1_plan"]["workouts"]:
        db.add(TrainingPlanWorkout(
            training_plan_id=training_plan_id,
            week_number=1,
            day_of_week=w["day"],
            workout_type=w["workout_type"],
            distance_meters=round(w["distance_km"] * 1000),
            pace_target=w["pace_target"],
            intensity_zone=w["intensity_zone"],
            purpose=w["purpose"],
        ))
