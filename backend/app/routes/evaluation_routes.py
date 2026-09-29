import statistics
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.models import PlanEvaluation, TrainingPlan
from app.schemas import (
    PlanEvaluationCreate,
    PlanEvaluationResponse,
    EvaluationStatsResponse,
    EvaluationCategoryStats,
    DimensionStats,
)

router = APIRouter(prefix="/evaluations", tags=["Research Evaluations"])

@router.post("", response_model=PlanEvaluationResponse, status_code=status.HTTP_201_CREATED)
def submit_evaluation(eval_in: PlanEvaluationCreate, db: Session = Depends(get_db)):
    """
    Submits a research evaluation for a generated training plan.
    Collects 1-5 Likert scale responses for:
    - Personalization
    - Usefulness
    - Clarity
    - Confidence in following the plan
    - Qualitative comments
    """
    # Verify training plan exists
    plan = db.query(TrainingPlan).filter(TrainingPlan.id == eval_in.training_plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Referenced training plan does not exist")

    eval_db = PlanEvaluation(
        training_plan_id=eval_in.training_plan_id,
        evaluated_plan_type=eval_in.evaluated_plan_type,
        personalization_score=eval_in.personalization_score,
        usefulness_score=eval_in.usefulness_score,
        clarity_score=eval_in.clarity_score,
        confidence_score=eval_in.confidence_score,
        comments=eval_in.comments
    )
    db.add(eval_db)
    db.commit()
    db.refresh(eval_db)

    return PlanEvaluationResponse(
        id=eval_db.id,
        training_plan_id=eval_db.training_plan_id,
        evaluated_plan_type=eval_db.evaluated_plan_type,
        personalization_score=eval_db.personalization_score,
        usefulness_score=eval_db.usefulness_score,
        clarity_score=eval_db.clarity_score,
        confidence_score=eval_db.confidence_score,
        comments=eval_db.comments,
        created_at=eval_db.created_at
    )


def _dimension_stats(values: List[int]) -> DimensionStats:
    """
    Mean is reported for N>=1, median for N>=1, and std_dev only for N>=2
    (a standard deviation of a single observation is undefined, not zero).
    """
    n = len(values)
    if n == 0:
        return DimensionStats(mean=None, median=None, std_dev=None)
    mean_val = round(statistics.mean(values), 3)
    median_val = round(statistics.median(values), 3)
    std_dev_val = round(statistics.stdev(values), 3) if n >= 2 else None
    return DimensionStats(mean=mean_val, median=median_val, std_dev=std_dev_val)


def compute_category_stats(eval_list: List[PlanEvaluation]) -> EvaluationCategoryStats:
    """
    Computes descriptive statistics for ONE evaluation group only (either
    rule_based or ai_personalized). This function never mixes the two groups
    together and never produces a cross-group comparison -- that stays a
    matter of researcher interpretation, not something the API asserts.
    """
    count = len(eval_list)
    personalization = _dimension_stats([e.personalization_score for e in eval_list])
    usefulness = _dimension_stats([e.usefulness_score for e in eval_list])
    clarity = _dimension_stats([e.clarity_score for e in eval_list])
    confidence = _dimension_stats([e.confidence_score for e in eval_list])

    overall_mean: Optional[float] = None
    if count > 0:
        all_scores = (
            [e.personalization_score for e in eval_list]
            + [e.usefulness_score for e in eval_list]
            + [e.clarity_score for e in eval_list]
            + [e.confidence_score for e in eval_list]
        )
        overall_mean = round(statistics.mean(all_scores), 3)

    return EvaluationCategoryStats(
        count=count,
        personalization=personalization,
        usefulness=usefulness,
        clarity=clarity,
        confidence=confidence,
        overall_mean=overall_mean,
    )

@router.get("/stats", response_model=EvaluationStatsResponse)
def get_evaluation_statistics(db: Session = Depends(get_db)):
    """
    Returns descriptive statistics (N, mean, median, std_dev per Likert
    dimension) for the research paper, disaggregated by 'rule_based' vs
    'ai_personalized' plans. The two groups are always reported separately;
    this endpoint deliberately does not compute or expose any combined
    "AI vs Rule-Based" score.
    """
    evals = db.query(PlanEvaluation).all()
    count = len(evals)

    rule_evals = [e for e in evals if getattr(e, "evaluated_plan_type", "ai_personalized") == "rule_based"]
    ai_evals = [e for e in evals if getattr(e, "evaluated_plan_type", "ai_personalized") == "ai_personalized"]

    rule_stats = compute_category_stats(rule_evals)
    ai_stats = compute_category_stats(ai_evals)

    recent_comments = [
        {
            "id": e.id,
            "training_plan_id": e.training_plan_id,
            "evaluated_plan_type": getattr(e, "evaluated_plan_type", "ai_personalized"),
            "scores": {
                "personalization": e.personalization_score,
                "usefulness": e.usefulness_score,
                "clarity": e.clarity_score,
                "confidence": e.confidence_score
            },
            "comments": e.comments,
            "created_at": e.created_at.isoformat()
        }
        for e in sorted(evals, key=lambda x: x.created_at, reverse=True)
        if e.comments
    ][:10]

    return EvaluationStatsResponse(
        total_evaluations=count,
        rule_based_stats=rule_stats,
        ai_personalized_stats=ai_stats,
        recent_comments=recent_comments
    )
