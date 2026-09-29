from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.core.rate_limit import limiter
from app.database import get_db
from app.models import User, WorkoutLog, TrainingPlanWorkout, TrainingPlan
from app.workouts.schemas import (
    WorkoutLogCreate,
    WorkoutLogUpdate,
    WorkoutLogResponse,
    WorkoutLogListResponse,
    WorkoutType,
)

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


@router.post("", response_model=WorkoutLogResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_WORKOUT_WRITE)
def create_workout(
    request: Request,
    payload: WorkoutLogCreate,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    _resolve_owned_training_plan_workout(db, payload.training_plan_workout_id, current_user)

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
    return WorkoutLogResponse.from_model(workout)


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
        items=[WorkoutLogResponse.from_model(w) for w in items],
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
    return WorkoutLogResponse.from_model(workout)


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
        _resolve_owned_training_plan_workout(db, updates["training_plan_workout_id"], current_user)

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
    return WorkoutLogResponse.from_model(workout)


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
