import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.database import get_db
from app.models import RunnerProfile, TrainingPlan
from app.schemas import RunnerProfileCreate, PlanGenerationResponse
from app.rules.generator import generate_rule_based_plan
from app.ai.llm_service import get_personalized_ai_plan

router = APIRouter(prefix="/plans", tags=["Training Plans"])

@router.post("/generate", response_model=PlanGenerationResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(profile_in: RunnerProfileCreate, db: Session = Depends(get_db)):
    """
    Core Hybrid Endpoint:
    1. Validates Runner Profile
    2. Runs Rule-Based Physiological & Periodization Engine (Jack Daniels VDOT + 80/20 Rule)
    3. Invokes Modular LLM to generate enriched personalized workouts within physiological constraints
    4. Persists runner profile and plan in SQLite database
    5. Returns both rule-based baseline and AI-personalized plan for research evaluation
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
def get_plan_by_id(plan_id: str, db: Session = Depends(get_db)):
    """Retrieves an existing generated training plan for review or evaluation."""
    plan_db = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
    if not plan_db:
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
    """Lists recent anonymous training plans."""
    plans = db.query(TrainingPlan).order_by(TrainingPlan.created_at.desc()).limit(limit).all()
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
