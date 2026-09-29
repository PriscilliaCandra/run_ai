import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User, WorkoutLog, TrainingPlan, TrainingPlanWorkout
from app.schemas import format_seconds_to_pace
from app.workouts.schemas import (
    DashboardSummaryResponse,
    PeriodTotals,
    ActivePlanSummary,
    TrainingPlanWorkoutResponse,
    WorkoutLogResponse,
    ProgressResponse,
)
from app.workouts.service import build_enriched_tpw_response, bucket_weekly_totals, generate_observations

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _period_totals(db: DBSession, user_id: str, start: date, end: date) -> PeriodTotals:
    """
    Purely descriptive sums/counts over non-deleted workouts in [start, end]
    (inclusive). No score, ranking, or predictive metric of any kind.
    Race-type workouts count toward every total (approved Phase 2 decision).
    Average pace is volume-weighted (total_duration / total_distance),
    never an unweighted average of individual workout paces.
    """
    rows = (
        db.query(WorkoutLog)
        .filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.deleted_at.is_(None),
            WorkoutLog.workout_date >= start,
            WorkoutLog.workout_date <= end,
        )
        .all()
    )
    run_count = len(rows)
    total_distance_m = sum(r.distance_meters for r in rows)
    total_duration_s = sum(r.duration_seconds for r in rows)

    avg_pace_display = None
    if total_distance_m > 0:
        pace_sec = round(total_duration_s / (total_distance_m / 1000.0))
        avg_pace_display = f"{format_seconds_to_pace(pace_sec)} /km"

    return PeriodTotals(
        total_distance_km=round(total_distance_m / 1000.0, 2),
        run_count=run_count,
        total_duration_seconds=total_duration_s,
        average_pace_display=avg_pace_display,
    )


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    today = date.today()

    # ISO calendar week: Monday-Sunday. Calendar month. No timezone
    # conversion anywhere -- pure calendar-date arithmetic on the server's
    # current date, matching workout_date's own no-timezone storage.
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)
    next_month_start = (
        today.replace(year=today.year + 1, month=1, day=1)
        if today.month == 12
        else today.replace(month=today.month + 1, day=1)
    )
    month_end = next_month_start - timedelta(days=1)

    this_week = _period_totals(db, current_user.id, week_start, week_end)
    this_month = _period_totals(db, current_user.id, month_start, month_end)

    recent = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.user_id == current_user.id, WorkoutLog.deleted_at.is_(None))
        .order_by(WorkoutLog.workout_date.desc(), WorkoutLog.created_at.desc())
        .limit(5)
        .all()
    )
    has_any_history = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.user_id == current_user.id, WorkoutLog.deleted_at.is_(None))
        .first()
        is not None
    )

    active_plan_row = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id == current_user.id, TrainingPlan.status == "active")
        .order_by(TrainingPlan.created_at.desc())
        .first()
    )

    active_plan = None
    if active_plan_row is not None:
        rule_plan = json.loads(active_plan_row.rule_based_plan_json)
        total_weeks = len(rule_plan.get("progression_schedule", [])) or 1
        plan_start = active_plan_row.start_date or active_plan_row.created_at.date()
        days_since_start = (today - plan_start).days
        raw_current_week = 1 if days_since_start < 0 else (days_since_start // 7) + 1
        current_week = min(max(1, raw_current_week), total_weeks)
        is_past_end = raw_current_week > total_weeks

        today_scheduled = None
        upcoming_scheduled = None
        current_week_completed_count = None
        current_week_total_loggable_count = None

        week_workouts = (
            db.query(TrainingPlanWorkout)
            .filter(
                TrainingPlanWorkout.training_plan_id == active_plan_row.id,
                TrainingPlanWorkout.week_number == current_week,
            )
            .all()
        )

        current_week_detail_available = len(week_workouts) > 0 and not is_past_end

        if current_week_detail_available:
            enriched = [
                build_enriched_tpw_response(db, tpw, plan_start, today, current_user.id)
                for tpw in week_workouts
            ]

            today_scheduled = next((e for e in enriched if e.scheduled_date == today), None)

            # Next non-rest-day scheduled workout strictly after today in current week
            future_non_rest = sorted(
                (e for e in enriched if e.scheduled_date > today and e.completion_status is not None),
                key=lambda e: e.scheduled_date,
            )
            upcoming_scheduled = future_non_rest[0] if future_non_rest else None

            loggable = [e for e in enriched if e.completion_status is not None]
            current_week_total_loggable_count = len(loggable)
            current_week_completed_count = sum(1 for e in loggable if e.completion_status == "completed")

        active_plan = ActivePlanSummary(
            plan_id=active_plan_row.id,
            target_race_distance=(
                active_plan_row.profile.target_race_distance if active_plan_row.profile else "N/A"
            ),
            target_pace_per_km=active_plan_row.target_pace,
            current_week=current_week,
            total_weeks=total_weeks,
            today_scheduled_workout=today_scheduled,
            current_week_detail_available=current_week_detail_available,
            upcoming_scheduled_workout=upcoming_scheduled,
            current_week_completed_count=current_week_completed_count,
            current_week_total_loggable_count=current_week_total_loggable_count,
        )

    return DashboardSummaryResponse(
        display_name=current_user.display_name,
        active_plan=active_plan,
        this_week=this_week,
        this_month=this_month,
        recent_activities=[WorkoutLogResponse.from_model(w) for w in recent],
        has_any_workout_history=has_any_history,
    )


# Phase 4: 7 = the fixed observation lookback (current week + 6 preceding
# weeks -- see PHASE_4_DESIGN.md Section 6.1). The fetch span is always at
# least this large so a single query can serve both the requested chart
# window and the observation computation, regardless of what `weeks` is.
_OBSERVATION_LOOKBACK_WEEKS = 7


@router.get("/progress", response_model=ProgressResponse)
def get_dashboard_progress(
    weeks: int = Query(8, ge=1, le=26),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """
    Deterministic weekly volume/consistency trend + at most 2 rule-based
    observation sentences -- see PHASE_4_DESIGN.md in full. Read-only: no
    row is ever written by this endpoint. Ownership is enforced by the
    single query below (WorkoutLog.user_id == current_user.id); `weeks` is
    the only client input and cannot express any identity.
    """
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())

    fetch_span_weeks = max(weeks, _OBSERVATION_LOOKBACK_WEEKS)
    range_start = current_week_start - timedelta(weeks=fetch_span_weeks - 1)
    range_end = current_week_start + timedelta(days=6)  # end of the current (partial) week

    # One ownership-scoped query serves both the chart data and the
    # observation computation -- see PHASE_4_DESIGN.md Section 12.
    rows = (
        db.query(WorkoutLog)
        .filter(
            WorkoutLog.user_id == current_user.id,
            WorkoutLog.deleted_at.is_(None),
            WorkoutLog.workout_date >= range_start,
            WorkoutLog.workout_date <= range_end,
        )
        .all()
    )

    all_buckets = bucket_weekly_totals(rows, range_start, fetch_span_weeks, today)
    observations = generate_observations(all_buckets[-_OBSERVATION_LOOKBACK_WEEKS:])

    return ProgressResponse(
        weeks=all_buckets[-weeks:],
        observations=observations,
    )
