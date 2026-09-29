import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends
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
)
from app.workouts.service import build_enriched_tpw_response

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
        current_week = max(1, ((today - plan_start).days // 7) + 1)
        current_week = min(current_week, total_weeks)
        # Detailed daily workouts are only materialized for week 1 -- see
        # PHASE_2_DESIGN.md Section 3.2. Never fabricate a workout for later weeks.
        week1_detail_available = current_week == 1

        today_scheduled = None
        upcoming_scheduled = None
        week1_completed_count = None
        week1_total_loggable_count = None

        if week1_detail_available:
            # Fetch and enrich all 7 week-1 rows once (Phase 3), rather than a
            # single today-only query -- needed for "upcoming" and the
            # completion count below, and cheaper than 7 separate round trips.
            all_week1 = (
                db.query(TrainingPlanWorkout)
                .filter(
                    TrainingPlanWorkout.training_plan_id == active_plan_row.id,
                    TrainingPlanWorkout.week_number == 1,
                )
                .all()
            )
            enriched = [
                build_enriched_tpw_response(db, tpw, active_plan_row.start_date, today, current_user.id)
                for tpw in all_week1
            ]

            today_name = today.strftime("%A")
            today_scheduled = next((e for e in enriched if e.day_of_week == today_name), None)

            # Next non-rest-day scheduled workout strictly after today, still
            # within week 1 -- purely descriptive, reuses data already fetched
            # above, no new endpoint or query pattern.
            future_non_rest = sorted(
                (e for e in enriched if e.scheduled_date > today and e.completion_status is not None),
                key=lambda e: e.scheduled_date,
            )
            upcoming_scheduled = future_non_rest[0] if future_non_rest else None

            # Week-1 completion count: a plain count of non-rest-day scheduled
            # workouts with a linked non-deleted log vs. the total non-rest-day
            # count -- never called an "adherence score" anywhere (see
            # PHASE_3_DESIGN.md Section 8.5).
            loggable = [e for e in enriched if e.completion_status is not None]
            week1_total_loggable_count = len(loggable)
            week1_completed_count = sum(1 for e in loggable if e.completion_status == "completed")

        active_plan = ActivePlanSummary(
            plan_id=active_plan_row.id,
            target_race_distance=(
                active_plan_row.profile.target_race_distance if active_plan_row.profile else "N/A"
            ),
            target_pace_per_km=active_plan_row.target_pace,
            current_week=current_week,
            total_weeks=total_weeks,
            today_scheduled_workout=today_scheduled,
            week1_detail_available=week1_detail_available,
            upcoming_scheduled_workout=upcoming_scheduled,
            week1_completed_count=week1_completed_count,
            week1_total_loggable_count=week1_total_loggable_count,
        )

    return DashboardSummaryResponse(
        display_name=current_user.display_name,
        active_plan=active_plan,
        this_week=this_week,
        this_month=this_month,
        recent_activities=[WorkoutLogResponse.from_model(w) for w in recent],
        has_any_workout_history=has_any_history,
    )
