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
from app.schemas import format_seconds_to_pace


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


def materialize_training_plan_workouts(db: DBSession, training_plan_id: str, rule_plan: Dict[str, Any]) -> None:
    """
    Creates TrainingPlanWorkout rows (7 per week, Monday through Sunday,
    including rest days) for all weeks in the deterministic rule-based plan.
    If 'weeks' is present in rule_plan, materializes all weeks (total_weeks * 7 rows).
    Otherwise falls back to week 1 for backward compatibility with legacy plans.
    """
    if "weeks" in rule_plan and rule_plan["weeks"]:
        for week_data in rule_plan["weeks"]:
            w_num = week_data["week_number"]
            for w in week_data["workouts"]:
                db.add(TrainingPlanWorkout(
                    training_plan_id=training_plan_id,
                    week_number=w_num,
                    day_of_week=w["day"],
                    workout_type=w["workout_type"],
                    distance_meters=round(w["distance_km"] * 1000),
                    pace_target=w["pace_target"],
                    intensity_zone=w["intensity_zone"],
                    purpose=w["purpose"],
                ))
    elif "week_1_plan" in rule_plan:
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


# Backwards compatibility alias
materialize_week_one = materialize_training_plan_workouts


def scheduled_date_for(plan_start_date: date, week_number_or_day: Any, day_of_week: Optional[str] = None) -> date:
    """
    Maps a training_plan_workout to its calendar date, accounting for week_number.
    Supports both:
      scheduled_date_for(plan_start_date, week_number, day_of_week)
      scheduled_date_for(plan_start_date, day_of_week)  # defaults to week_number=1
    """
    if day_of_week is None:
        week_number = 1
        day_name = str(week_number_or_day)
    else:
        week_number = int(week_number_or_day)
        day_name = day_of_week

    target_idx = DAYS_OF_WEEK.index(day_name)
    offset = (target_idx - plan_start_date.weekday()) % 7
    week_anchor = plan_start_date + timedelta(weeks=week_number - 1)
    return week_anchor + timedelta(days=offset)


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

    sched_date = scheduled_date_for(plan_start_date, tpw.week_number, tpw.day_of_week)

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


def bucket_weekly_totals(
    rows: List[WorkoutLog],
    range_start: date,
    num_weeks: int,
    today: date,
) -> List["WeeklyProgressBucket"]:
    """
    Buckets already-fetched WorkoutLog rows into exactly num_weeks ISO
    calendar weeks (Monday-Sunday) starting at range_start, oldest first.
    Pure function -- no database access -- see PHASE_4_DESIGN.md Sections
    4-5 and 8. `rows` is expected to already be scoped to the current user
    and non-deleted by the caller's query; this function does not filter by
    ownership or deletion itself.

    Every week is returned, including weeks with zero matching rows
    (zero-valued, never omitted -- PHASE_4_DESIGN.md Section 4). The single
    week containing `today` is marked is_current_week=True; since no future
    week is ever produced, this is the only week that can ever be partial.
    """
    from app.workouts.schemas import WeeklyProgressBucket

    current_week_start = today - timedelta(days=today.weekday())

    buckets: List[WeeklyProgressBucket] = []
    for i in range(num_weeks):
        week_start = range_start + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        week_rows = [r for r in rows if week_start <= r.workout_date <= week_end]

        run_count = len(week_rows)
        total_distance_m = sum(r.distance_meters for r in week_rows)
        total_duration_s = sum(r.duration_seconds for r in week_rows)
        logged_days_count = len({r.workout_date for r in week_rows})

        avg_pace_display = None
        if total_distance_m > 0:
            pace_sec = round(total_duration_s / (total_distance_m / 1000.0))
            avg_pace_display = f"{format_seconds_to_pace(pace_sec)} /km"

        buckets.append(WeeklyProgressBucket(
            week_start=week_start,
            week_end=week_end,
            is_current_week=(week_start == current_week_start),
            total_distance_km=round(total_distance_m / 1000.0, 2),
            total_duration_seconds=total_duration_s,
            run_count=run_count,
            logged_days_count=logged_days_count,
            average_pace_display=avg_pace_display,
        ))
    return buckets


# Fixed thresholds for generate_observations() -- see PHASE_4_DESIGN.md
# Section 6. Every value here is a deliberate, documented decision, not a
# tuned/guessed constant -- changing any of these is a design change, not a
# bug fix.
_OBSERVATION_WINDOW_WEEKS = 3
_VOLUME_MIN_RUN_COUNT_PER_WINDOW = 2
_VOLUME_MIN_PRIOR_TOTAL_KM = 5.0
_VOLUME_PERCENT_THRESHOLD = 10.0
_CONSISTENCY_MIN_PRIOR_DAYS_TOTAL = 3
_CONSISTENCY_DAY_DIFFERENCE_THRESHOLD = 2


def generate_observations(buckets: List["WeeklyProgressBucket"]) -> List[str]:
    """
    Deterministic, template-based observation sentences -- see
    PHASE_4_DESIGN.md Section 6 for the full rationale behind every
    threshold. Never an LLM call, never a score, never a prediction, never a
    quality judgment ("better"/"worse"/"good"/"bad" do not appear).

    Expects exactly the trailing 7 weekly buckets (the current week plus the
    6 weeks immediately before it), oldest first -- i.e. buckets[-1] is the
    current (partial) week, which is deliberately excluded from both
    comparison windows. Returns an empty list (not an error) whenever there
    isn't enough historical data for either observation to be eligible --
    "insufficient data" and "no trend" are represented identically, by
    absence (PHASE_4_DESIGN.md Section 6.4).
    """
    if len(buckets) < 1 + 2 * _OBSERVATION_WINDOW_WEEKS:
        return []

    # buckets[-1] is the current (partial) week -- excluded entirely.
    recent = buckets[-1 - _OBSERVATION_WINDOW_WEEKS:-1]
    prior = buckets[-1 - 2 * _OBSERVATION_WINDOW_WEEKS:-1 - _OBSERVATION_WINDOW_WEEKS]

    observations: List[str] = []

    # -- Observation 1: weekly volume trend --
    # Summed from each bucket's own already-rounded (2 decimal places)
    # total_distance_km -- the same precision already exposed in the public
    # API response -- so the comparison never disagrees with what a caller
    # could independently recompute from the returned `weeks` array.
    prior_run_count = sum(b.run_count for b in prior)
    recent_run_count = sum(b.run_count for b in recent)
    prior_total_km = sum(b.total_distance_km for b in prior)
    recent_total_km = sum(b.total_distance_km for b in recent)

    if (
        prior_run_count >= _VOLUME_MIN_RUN_COUNT_PER_WINDOW
        and recent_run_count >= _VOLUME_MIN_RUN_COUNT_PER_WINDOW
        and prior_total_km >= _VOLUME_MIN_PRIOR_TOTAL_KM
    ):
        percent_change = (recent_total_km - prior_total_km) / prior_total_km * 100.0
        if percent_change >= _VOLUME_PERCENT_THRESHOLD:
            observations.append(
                "Your weekly running distance has increased over the last 3 weeks "
                "compared to the 3 weeks before that."
            )
        elif percent_change <= -_VOLUME_PERCENT_THRESHOLD:
            observations.append(
                "Your weekly running distance has decreased over the last 3 weeks "
                "compared to the 3 weeks before that."
            )

    # -- Observation 2: logging-consistency trend --
    prior_days_total = sum(b.logged_days_count for b in prior)
    recent_days_total = sum(b.logged_days_count for b in recent)

    if prior_days_total >= _CONSISTENCY_MIN_PRIOR_DAYS_TOTAL:
        day_difference = recent_days_total - prior_days_total
        if day_difference >= _CONSISTENCY_DAY_DIFFERENCE_THRESHOLD:
            observations.append(
                "You've logged workouts on more days over the last 3 weeks "
                "compared to the 3 weeks before that."
            )
        elif day_difference <= -_CONSISTENCY_DAY_DIFFERENCE_THRESHOLD:
            observations.append(
                "You've logged workouts on fewer days over the last 3 weeks "
                "compared to the 3 weeks before that."
            )

    # Fixed priority order (volume before consistency) and hard cap of 2 --
    # both already guaranteed by construction above (at most one string per
    # observation type, appended in this fixed order), asserted here as a
    # belt-and-suspenders safeguard against a future edit accidentally
    # adding a third observation type without updating this cap.
    return observations[:2]
