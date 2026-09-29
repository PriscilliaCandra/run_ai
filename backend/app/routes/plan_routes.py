import json
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.auth.dependencies import get_optional_current_user
from app.core.rate_limit import limiter, _current_user_or_ip_key
from app.config import settings
from app.database import get_db
from app.models import RunnerProfile, TrainingPlan, User
from app.schemas import RunnerProfileCreate, PlanGenerationResponse
from app.rules.generator import generate_rule_based_plan
from app.ai.llm_service import get_personalized_ai_plan

router = APIRouter(prefix="/plans", tags=["Training Plans"])

@router.post("/generate", response_model=PlanGenerationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_PLAN_GENERATION, key_func=_current_user_or_ip_key)
async def generate_plan(
    request: Request,
    profile_in: RunnerProfileCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Core Hybrid Endpoint:
    1. Validates Runner Profile
    2. Runs Rule-Based Physiological & Periodization Engine (Jack Daniels VDOT + 80/20 Rule)
    3. Invokes Modular LLM to generate enriched personalized workouts within physiological constraints
    4. Persists runner profile and plan in SQLite database
    5. Returns both rule-based baseline and AI-personalized plan for research evaluation

    Ownership: if the request carries a valid session, the created plan is
    attached to that user (user_id set). Anonymous requests (no session --
    the existing, unchanged research flow) always produce a plan with
    user_id = NULL, exactly as before. A plan is never retroactively
    attached to a user after the fact, and the client can never set
    user_id itself -- it is derived solely from the authenticated session.
    """
    # 1. Run deterministic rule-based training recommendation
    rule_plan = generate_rule_based_plan(profile_in)

    # 2. Run modular AI personalization
    ai_plan, model_used = await get_personalized_ai_plan(profile_in, rule_plan)

    # 3. Persist runner profile (anonymous ID, no personal identifying info)
    profile_db = RunnerProfile(
        age=profile_in.age,
        gender=profile_in.gender,
        experience_level=profile_in.experience_level,
        pb_5k=profile_in.pb_5k,
        pb_10k=profile_in.pb_10k,
        target_race_distance=profile_in.target_race_distance,
        target_race_time=profile_in.target_race_time,
        current_weekly_mileage=profile_in.current_weekly_mileage,
        training_days_per_week=profile_in.training_days_per_week,
        preferred_training_days=",".join(profile_in.preferred_training_days),
        plan_duration_weeks=profile_in.plan_duration_weeks,
        injury_limitations=profile_in.injury_limitations,
        easy_run_pace=profile_in.easy_run_pace
    )
    db.add(profile_db)
    db.flush()

    # 4. Persist generated plan with both baseline and AI versions
    plan_db = TrainingPlan(
        runner_profile_id=profile_db.id,
        user_id=current_user.id if current_user else None,
        calculated_vdot=rule_plan["vdot"],
        target_pace=rule_plan["target_pace_per_km"],
        rule_based_plan_json=json.dumps(rule_plan),
        ai_plan_json=json.dumps(ai_plan),
        explainability_summary=json.dumps(rule_plan["explainability"]),
        ai_model_used=model_used
    )
    db.add(plan_db)
    db.commit()
    db.refresh(plan_db)

    return PlanGenerationResponse(
        plan_id=plan_db.id,
        runner_profile_id=profile_db.id,
        calculated_vdot=rule_plan["vdot"],
        target_pace_per_km=rule_plan["target_pace_per_km"],
        rule_based_plan=rule_plan,
        ai_personalized_plan=ai_plan,
        explainability=rule_plan["explainability"],
        ai_model_used=model_used,
        created_at=plan_db.created_at
    )


@router.get("/{plan_id}", response_model=PlanGenerationResponse)
def get_plan_by_id(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Retrieves an existing generated training plan.

    Ownership: an anonymous research plan (user_id IS NULL) remains
    reachable without authentication, exactly as before -- this is the
    existing research flow and must not require login. A user-owned plan
    (user_id IS NOT NULL) is only returned to that same authenticated user;
    anyone else (including another logged-in user or an anonymous caller)
    gets the same generic 404 a nonexistent plan would return, so the
    endpoint never reveals whether a given ID belongs to someone else.
    """
    plan_db = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
    if not plan_db:
        raise HTTPException(status_code=404, detail="Training plan not found")

    if plan_db.user_id is not None:
        if current_user is None or current_user.id != plan_db.user_id:
            raise HTTPException(status_code=404, detail="Training plan not found")

    return PlanGenerationResponse(
        plan_id=plan_db.id,
        runner_profile_id=plan_db.runner_profile_id,
        calculated_vdot=plan_db.calculated_vdot,
        target_pace_per_km=plan_db.target_pace,
        rule_based_plan=json.loads(plan_db.rule_based_plan_json),
        ai_personalized_plan=json.loads(plan_db.ai_plan_json),
        explainability=json.loads(plan_db.explainability_summary),
        ai_model_used=plan_db.ai_model_used,
        created_at=plan_db.created_at
    )


@router.get("", response_model=List[Dict[str, Any]])
def list_recent_plans(db: Session = Depends(get_db), limit: int = 10):
    """
    Lists recent ANONYMOUS (research) training plans only -- matches this
    endpoint's original research purpose. User-owned plans (user_id IS NOT
    NULL) are deliberately excluded here so a public/unauthenticated caller
    can never enumerate other users' plans through this listing.
    """
    plans = (
        db.query(TrainingPlan)
        .filter(TrainingPlan.user_id.is_(None))
        .order_by(TrainingPlan.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for p in plans:
        results.append({
            "plan_id": p.id,
            "calculated_vdot": p.calculated_vdot,
            "target_pace": p.target_pace,
            "ai_model_used": p.ai_model_used,
            "created_at": p.created_at,
            "race_distance": p.profile.target_race_distance if p.profile else "N/A",
            "target_time": p.profile.target_race_time if p.profile else "N/A",
        })
    return results
