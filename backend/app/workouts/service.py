"""
Consumer plan lifecycle helpers, used only from the authenticated branch of
plan generation (app/routes/plan_routes.py). Never called for anonymous
research plan generation -- research plans never get a status/start_date
or any training_plan_workouts rows.

Also holds the Phase 3 plan<->actual-workout derivation helpers (scheduled
date mapping, completion-state derivation). None of these persist anything
-- see PHASE_3_DESIGN.md Sections 5.A and 8 for the full rationale: every
value here is recomputed on every read, never stored.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session as DBSession

from app.models import TrainingPlan, TrainingPlanWorkout, WorkoutLog
from app.rules.generator import DAYS_OF_WEEK


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


def scheduled_date_for(plan_start_date: date, day_of_week: str) -> date:
    """
    Maps a training_plan_workout's day_of_week label (a weekday NAME, e.g.
    "Wednesday") to the one actual calendar date it represents in week 1,
    given the plan's start_date. Every weekday name appears exactly once in
    any 7 consecutive calendar days starting at start_date, so this is
    always well-defined regardless of which weekday start_date itself falls
    on (Monday, mid-week, or Sunday are all handled identically by this
    formula) -- see PHASE_3_DESIGN.md Section 5.A.
    """
    target_idx = DAYS_OF_WEEK.index(day_of_week)
    offset = (target_idx - plan_start_date.weekday()) % 7
    return plan_start_date + timedelta(days=offset)


def is_rest_day(workout_type: str) -> bool:
    """Matches the same convention already used by the frontend's WorkoutCard
    (workout.workout_type.toLowerCase().includes('rest'))."""
    return "rest" in workout_type.lower()


def derive_completion_status(scheduled_for: date, today: date, has_active_log: bool) -> Optional[str]:
    """
    Derived, never stored (PHASE_3_DESIGN.md Section 8). The caller is
    responsible for passing None through for rest days (see is_rest_day)
    rather than calling this at all for them.
    """
    if has_active_log:
        return "completed"
    if scheduled_for < today:
        return "missed"
    return "scheduled"


def build_enriched_tpw_response(
    db: DBSession,
    tpw: TrainingPlanWorkout,
    plan_start_date: date,
    today: date,
    owner_user_id: str,
):
    """
    Builds a fully enriched TrainingPlanWorkoutResponse for a single
    scheduled workout: scheduled_date, derived completion_status, and the
    list of non-deleted workout_logs linked to it.

    Security note (see PHASE_3_DESIGN.md Section 18, "indirect IDOR" case):
    the linked-logs query is scoped by BOTH training_plan_workout_id AND
    user_id == owner_user_id. A log can only ever have this
    training_plan_workout_id if it was created by a request that already
    passed the ownership check in _resolve_owned_training_plan_workout (so
    in practice user_id already always matches) -- the explicit user_id
    filter here is defense-in-depth, not the only thing preventing leakage.
    """
    from app.workouts.schemas import TrainingPlanWorkoutResponse, WorkoutLogResponse

    sched_date = scheduled_date_for(plan_start_date, tpw.day_of_week)

    logs: List[WorkoutLog] = (
        db.query(WorkoutLog)
        .filter(
            WorkoutLog.training_plan_workout_id == tpw.id,
            WorkoutLog.user_id == owner_user_id,
            WorkoutLog.deleted_at.is_(None),
        )
        .order_by(WorkoutLog.created_at.asc())
        .all()
    )

    status = None if is_rest_day(tpw.workout_type) else derive_completion_status(sched_date, today, len(logs) > 0)

    return TrainingPlanWorkoutResponse.from_model(
        tpw,
        scheduled_date=sched_date,
        completion_status=status,
        linked_workout_logs=[WorkoutLogResponse.from_model(l) for l in logs],
    )
