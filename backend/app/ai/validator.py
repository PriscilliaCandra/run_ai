from typing import Any, Dict

from pydantic import ValidationError

from app.ai.schemas import AIPersonalizedPlan
from app.schemas import RunnerProfileCreate

# Tolerances account for floating point rounding introduced when the LLM
# echoes back numbers as JSON, not for genuine deviation from the baseline.
DISTANCE_TOLERANCE_KM = 0.05
MILEAGE_TOLERANCE_KM = 0.15


class AIPlanValidationError(Exception):
    """
    Raised when raw LLM output either fails schema validation or silently
    changes a numerical value that must be controlled exclusively by the
    deterministic rule-based engine (distances, paces, weekly mileage,
    workout/rest day counts). The caller must treat this as "never trust
    the AI plan" and fall back to the offline rule-constrained synthesizer.
    """


def validate_ai_plan(
    raw_plan: Dict[str, Any],
    rule_plan: Dict[str, Any],
    profile: RunnerProfileCreate,
) -> AIPersonalizedPlan:
    """
    Validates a raw (already JSON-parsed) LLM plan against the deterministic
    rule-based baseline for the same runner profile.

    The AI is allowed to personalize purely textual/explanatory fields
    (coach_overview, warmup_cooldown, workout_execution, recovery_instruction,
    purpose, personalized_insights, ai_personalization_summary,
    why_this_plan_was_generated). It must NOT change any physiologically
    derived numerical value: workout count, workout type, distance, pace,
    intensity zone, weekly mileage, or the number of training/rest days.

    Raises AIPlanValidationError on any schema or constraint violation.
    """
    try:
        parsed = AIPersonalizedPlan.model_validate(raw_plan)
    except ValidationError as e:
        raise AIPlanValidationError(f"schema validation failed ({e.error_count()} error(s))") from e

    baseline_workouts = rule_plan["week_1_plan"]["workouts"]
    baseline_by_day = {w["day"]: w for w in baseline_workouts}

    if len(parsed.workouts) != len(baseline_workouts):
        raise AIPlanValidationError(
            f"workout count mismatch: expected {len(baseline_workouts)}, got {len(parsed.workouts)}"
        )

    seen_days = set()
    for w in parsed.workouts:
        baseline_w = baseline_by_day.get(w.day)
        if baseline_w is None:
            raise AIPlanValidationError(f"unrecognized day '{w.day}' not present in the rule-based baseline")
        if w.day in seen_days:
            raise AIPlanValidationError(f"duplicate day '{w.day}' in AI plan")
        seen_days.add(w.day)

        if w.workout_type.strip().lower() != baseline_w["workout_type"].strip().lower():
            raise AIPlanValidationError(
                f"workout_type changed on {w.day}: expected '{baseline_w['workout_type']}', got '{w.workout_type}'"
            )
        if abs(w.distance_km - baseline_w["distance_km"]) > DISTANCE_TOLERANCE_KM:
            raise AIPlanValidationError(
                f"distance_km changed on {w.day}: expected {baseline_w['distance_km']}, got {w.distance_km}"
            )
        if w.pace_target.strip() != baseline_w["pace_target"].strip():
            raise AIPlanValidationError(
                f"pace_target changed on {w.day}: expected '{baseline_w['pace_target']}', got '{w.pace_target}'"
            )
        if w.intensity_zone.strip() != baseline_w["intensity_zone"].strip():
            raise AIPlanValidationError(
                f"intensity_zone changed on {w.day}: expected '{baseline_w['intensity_zone']}', got '{w.intensity_zone}'"
            )

    missing_days = set(baseline_by_day.keys()) - seen_days
    if missing_days:
        raise AIPlanValidationError(f"missing day(s) in AI plan: {sorted(missing_days)}")

    expected_mileage = rule_plan["week_1_plan"]["weekly_mileage_km"]
    if abs(parsed.weekly_mileage_km - expected_mileage) > MILEAGE_TOLERANCE_KM:
        raise AIPlanValidationError(
            f"weekly_mileage_km changed: expected {expected_mileage}, got {parsed.weekly_mileage_km}"
        )

    expected_rest_days = 7 - profile.training_days_per_week
    actual_rest_days = sum(1 for w in parsed.workouts if w.workout_type.strip().lower() == "rest & recovery")
    if actual_rest_days != expected_rest_days:
        raise AIPlanValidationError(
            f"rest day count mismatch: expected {expected_rest_days}, got {actual_rest_days}"
        )

    actual_training_days = len(parsed.workouts) - actual_rest_days
    if actual_training_days != profile.training_days_per_week:
        raise AIPlanValidationError(
            f"training day count mismatch: expected {profile.training_days_per_week}, got {actual_training_days}"
        )

    # Re-order to match the baseline's Monday->Sunday sequence so the UI grid
    # stays consistent regardless of the order the LLM emitted workouts in.
    by_day = {w.day: w for w in parsed.workouts}
    parsed.workouts = [by_day[day] for day in baseline_by_day.keys()]

    return parsed
