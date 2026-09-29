from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.models import User, WorkoutLog, TrainingPlanWorkout, TrainingPlan
from app.workouts.schemas import (
    ScheduledWorkoutSummary,
    WorkoutLogCreate,
    WorkoutLogUpdate,
    WorkoutLogResponse,
    WorkoutLogListResponse,
    WorkoutType,
)
from app.workouts.service import is_rest_day, scheduled_date_for

router = APIRouter(prefix="/workouts", tags=["Workouts"])


def _resolve_owned_training_plan_workout(
    db: DBSession, training_plan_workout_id: Optional[str], current_user: User
) -> Optional[TrainingPlanWorkout]:
    """
    CRITICAL SECURITY CHECK. A client may reference a scheduled workout by
    ID, but ownership is verified independently by the server by walking
    training_plan_workout -> training_plan -> training_plan.user_id and
    comparing to the authenticated user -- training_plan_workout_id,
    training_plan_id, and user_id are never trusted from the client as
    ownership authority, only this server-side join is.
    """
    if training_plan_workout_id is None:
        return None
    tpw = (
        db.query(TrainingPlanWorkout)
        .join(TrainingPlan, TrainingPlanWorkout.training_plan_id == TrainingPlan.id)
        .filter(
            TrainingPlanWorkout.id == training_plan_workout_id,
            TrainingPlan.user_id == current_user.id,
        )
        .first()
    )
    if tpw is None:
        # Same generic error whether it doesn't exist or belongs to someone else's plan.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid training_plan_workout_id.")
    return tpw


def _get_owned_workout_or_404(db: DBSession, workout_id: str, current_user: User) -> WorkoutLog:
    workout = (
        db.query(WorkoutLog)
        .filter(
            WorkoutLog.id == workout_id,
            WorkoutLog.user_id == current_user.id,
            WorkoutLog.deleted_at.is_(None),
        )
        .first()
    )
    if workout is None:
        # Generic 404 whether it doesn't exist, belongs to someone else, or was soft-deleted.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found.")
    return workout


def _reject_if_archived(db: DBSession, tpw: TrainingPlanWorkout) -> None:
    """
    Phase 3 locked decision: a NEW link to a scheduled workout on an
    archived plan is rejected. Existing (historical) links made while the
    plan was still active are never touched or invalidated by this check --
    it only runs at the moment a client is trying to attach a link, never
    when merely reading one back. Does not, and must not, reactivate the
    plan or otherwise mutate training_plans in any way.
    """
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == tpw.training_plan_id).first()
    if plan is not None and plan.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This training plan is archived and can no longer accept new workout links.",
        )


def _linked_scheduled_workout_summary(db: DBSession, workout: WorkoutLog) -> Optional[ScheduledWorkoutSummary]:
    """
    Builds the (always-"completed", or None for a rest day) scheduled-workout
    summary attached to a single WorkoutLogResponse -- see
    ScheduledWorkoutSummary's own docstring for why the status never needs
    to be derived here: `workout` itself, being the non-deleted log passed
    in, IS the fulfilling log for its own training_plan_workout_id.
    """
    if not workout.training_plan_workout_id:
        return None
    tpw = db.query(TrainingPlanWorkout).filter(TrainingPlanWorkout.id == workout.training_plan_workout_id).first()
    if tpw is None:
        return None
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == tpw.training_plan_id).first()
    if plan is None or plan.start_date is None:
        return None
    sched_date = scheduled_date_for(plan.start_date, tpw.day_of_week)
    completion_status = None if is_rest_day(tpw.workout_type) else "completed"
    return ScheduledWorkoutSummary.from_tpw(tpw, sched_date, completion_status)


def _build_workout_response(db: DBSession, workout: WorkoutLog) -> WorkoutLogResponse:
    return WorkoutLogResponse.from_model(workout, linked_scheduled_workout=_linked_scheduled_workout_summary(db, workout))


def _build_workout_responses_batch(db: DBSession, items: List[WorkoutLog]) -> List[WorkoutLogResponse]:
    """Batch variant of _build_workout_response for a paginated list -- avoids
    N+1 queries by resolving all referenced scheduled workouts/plans in two
    extra queries total, regardless of page size."""
    tpw_ids = {w.training_plan_workout_id for w in items if w.training_plan_workout_id}
    if not tpw_ids:
        return [WorkoutLogResponse.from_model(w) for w in items]

    tpw_rows = {t.id: t for t in db.query(TrainingPlanWorkout).filter(TrainingPlanWorkout.id.in_(tpw_ids)).all()}
    plan_ids = {t.training_plan_id for t in tpw_rows.values()}
    plan_rows = {p.id: p for p in db.query(TrainingPlan).filter(TrainingPlan.id.in_(plan_ids)).all()}

    summaries: Dict[str, ScheduledWorkoutSummary] = {}
    for tpw_id, tpw in tpw_rows.items():
        plan = plan_rows.get(tpw.training_plan_id)
        if plan is None or plan.start_date is None:
            continue
        sched_date = scheduled_date_for(plan.start_date, tpw.day_of_week)
        completion_status = None if is_rest_day(tpw.workout_type) else "completed"
        summaries[tpw_id] = ScheduledWorkoutSummary.from_tpw(tpw, sched_date, completion_status)

    return [
        WorkoutLogResponse.from_model(w, linked_scheduled_workout=summaries.get(w.training_plan_workout_id))
        for w in items
    ]


@router.post("", response_model=WorkoutLogResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_WORKOUT_WRITE)
def create_workout(
    request: Request,
    payload: WorkoutLogCreate,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    tpw = _resolve_owned_training_plan_workout(db, payload.training_plan_workout_id, current_user)
    if tpw is not None:
        # Creating a workout is always establishing a brand-new link (the
        # workout doesn't exist yet), so the archived-plan rule always
        # applies here -- see PHASE_3_DESIGN.md / the Phase 3 brief, Section 7.
        _reject_if_archived(db, tpw)

    workout = WorkoutLog(
        user_id=current_user.id,  # from the session only -- never from the request body
        workout_date=payload.workout_date,
        distance_meters=payload.distance_meters,
        duration_seconds=payload.duration_seconds,
        workout_type=payload.workout_type.value,
        avg_heart_rate=payload.avg_heart_rate,
        max_heart_rate=payload.max_heart_rate,
        cadence_spm=payload.cadence_spm,
        elevation_gain_m=payload.elevation_gain_m,
        rpe=payload.rpe,
        notes=payload.notes,
        training_plan_workout_id=payload.training_plan_workout_id,
    )
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return _build_workout_response(db, workout)


@router.get("", response_model=WorkoutLogListResponse)
def list_workouts(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    workout_type: Optional[WorkoutType] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    query = db.query(WorkoutLog).filter(
        WorkoutLog.user_id == current_user.id,
        WorkoutLog.deleted_at.is_(None),
    )
    if date_from:
        query = query.filter(WorkoutLog.workout_date >= date_from)
    if date_to:
        query = query.filter(WorkoutLog.workout_date <= date_to)
    if workout_type:
        query = query.filter(WorkoutLog.workout_type == workout_type.value)

    total = query.count()
    items = (
        query.order_by(WorkoutLog.workout_date.desc(), WorkoutLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return WorkoutLogListResponse(
        items=_build_workout_responses_batch(db, items),
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{workout_id}", response_model=WorkoutLogResponse)
def get_workout(
    workout_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    workout = _get_owned_workout_or_404(db, workout_id, current_user)
    return _build_workout_response(db, workout)


@router.patch("/{workout_id}", response_model=WorkoutLogResponse)
@limiter.limit(settings.RATE_LIMIT_WORKOUT_WRITE)
def update_workout(
    request: Request,
    workout_id: str,
    payload: WorkoutLogUpdate,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    workout = _get_owned_workout_or_404(db, workout_id, current_user)
    updates = payload.model_dump(exclude_unset=True)

    if "training_plan_workout_id" in updates:
        new_id = updates["training_plan_workout_id"]
        # Ownership is re-verified unconditionally for any non-null id, exactly
        # as Phase 2 already did -- this is not weakened or bypassed below.
        tpw = _resolve_owned_training_plan_workout(db, new_id, current_user)
        # The archived-plan rule (Section 7) only blocks a GENUINELY NEW link.
        # Re-sending the workout's own already-linked id (e.g. a form that
        # resubmits the full object unchanged) must not be rejected just
        # because the plan has since been archived -- that would break an
        # existing historical link, which is explicitly required to survive.
        # Setting it to null (unlinking) is never subject to this rule either.
        is_new_link = new_id is not None and new_id != workout.training_plan_workout_id
        if is_new_link and tpw is not None:
            _reject_if_archived(db, tpw)

    # Re-validate heart-rate order against the MERGED (existing + incoming)
    # values -- a partial update might only touch one of the two HR fields.
    new_avg = updates.get("avg_heart_rate", workout.avg_heart_rate)
    new_max = updates.get("max_heart_rate", workout.max_heart_rate)
    if new_avg is not None and new_max is not None and new_avg > new_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="avg_heart_rate: Average heart rate cannot exceed max heart rate.",
        )

    for field, value in updates.items():
        if field == "workout_type" and value is not None:
            value = value.value if hasattr(value, "value") else value
        setattr(workout, field, value)

    db.commit()
    db.refresh(workout)
    return _build_workout_response(db, workout)


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_WORKOUT_WRITE)
def delete_workout(
    request: Request,
    workout_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    workout = _get_owned_workout_or_404(db, workout_id, current_user)
    workout.deleted_at = datetime.utcnow()  # soft delete only -- never a physical DELETE
    db.commit()
    return None
