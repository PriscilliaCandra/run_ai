import json
from typing import Dict, Any
from app.schemas import RunnerProfileCreate

SYSTEM_PROMPT = """You are an AI-based Running Coach and Sports Scientist assisting in an academic research project titled:
'Design and Evaluation of an AI-Based Personalized Running Training Recommendation System'.

Your goal is to personalize and enrich a physiologically validated, rule-based running training plan.

CRITICAL INSTRUCTIONS:
1. STRICT CONSTRAINT PRESERVATION: You MUST respect the predefined training parameters (weekly mileage, workout days, and calculated pace zones). Do NOT invent arbitrary paces or excessive mileage surges.
2. ENHANCED PERSONALIZATION: Personalize the workout descriptions, warm-up/cool-down instructions, mental coaching cues, and execution advice based on the runner's age, experience level, goal race, and any reported injury/limitation.
3. EXPLAINABILITY: Clearly articulate WHY specific workouts are prescribed and HOW the runner's profile parameters influenced the final recommendations.
4. SAFETY & MEDICAL DISCLAIMER: Emphasize that recommendations are educational, not medical advice, and prompt the user to stop if acute pain occurs.
5. STRICT JSON OUTPUT: Return ONLY a valid JSON object matching the requested schema without markdown wrapping or backticks.
"""

def build_user_prompt(profile: RunnerProfileCreate, rule_plan: Dict[str, Any]) -> str:
    payload = {
        "runner_profile": {
            "age": profile.age,
            "gender": profile.gender,
            "experience_level": profile.experience_level,
            "current_5k_pb": profile.pb_5k,
            "optional_10k_pb": profile.pb_10k,
            "target_race_distance": profile.target_race_distance,
            "target_race_time": profile.target_race_time,
            "current_weekly_mileage_km": profile.current_weekly_mileage,
            "training_days_per_week": profile.training_days_per_week,
            "preferred_training_days": profile.preferred_training_days,
            "plan_duration_weeks": profile.plan_duration_weeks,
            "injury_limitations": profile.injury_limitations or "None reported",
            "easy_run_pace": profile.easy_run_pace
        },
        "physiological_parameters": {
            "calculated_vdot": rule_plan["vdot"],
            "target_race_pace_per_km": rule_plan["target_pace_per_km"],
            "training_pace_zones": rule_plan["paces"]
        },
        "rule_based_baseline_week": rule_plan["week_1_plan"]
    }

    instructions = """
Please generate the personalized AI training plan based on the structured input above.

CRITICAL NUMERICAL PRESERVATION RULE:
You MUST keep the exact distance_km, weekly_mileage_km, workout_type, and pace_target provided in the rule_based_baseline_week.
Do NOT modify the workout distances or pace numbers.
Your role is to personalize:
1. Warm-up and cool-down protocols tailored to the runner's experience level.
2. Step-by-step workout executions with sensory and mental pacing cues.
3. Concrete adaptations for any reported injury or biomechanical limitation.
4. Explanations of why sessions are sequenced on the runner's preferred days.

Format your output as a valid JSON object with the following structure:
{
  "coach_overview": "A warm, motivating 2-3 paragraph personalized introduction addressing the runner's specific profile and goal.",
  "weekly_mileage_km": <exact float from baseline week>,
  "workouts": [
    {
      "day": "Monday",
      "workout_type": "<exact workout_type from baseline>",
      "distance_km": <exact distance_km from baseline>,
      "pace_target": "<exact pace_target from baseline>",
      "intensity_zone": "<exact intensity_zone from baseline>",
      "warmup_cooldown": "<Explicit warm-up and cool-down protocol personalized for runner's experience>",
      "workout_execution": "<Detailed step-by-step description with mental pacing cues and cadence focus>",
      "recovery_instruction": "<Hydration, nutrition, and post-run recovery guidance>",
      "purpose": "<Why this workout is critical for their specific race target>"
    }
  ],
  "personalized_insights": {
    "pacing_strategy": "<Specific advice on managing paces during training without exceeding threshold>",
    "injury_prevention_note": "<Tailored advice addressing reported injury limitations or general runner durability>",
    "nutrition_and_recovery_advice": "<Key recovery recommendations for their training frequency>"
  },
  "ai_personalization_summary": [
    "Training frequency was adapted to X available training days per week.",
    "Workout days were aligned with the runner's preferred training schedule.",
    "Warm-up and pacing guidance were personalized based on the runner's experience level.",
    "Specific biomechanical precautions integrated for reported limitation."
  ],
  "why_this_plan_was_generated": {
    "key_influencing_factors": [
      "<Factor 1: 5K PB determined VDOT and pace zones>",
      "<Factor 2: Current weekly mileage constrained baseline volume>",
      "<Factor 3: Available days structured into polarized aerobic and quality>",
      "<Factor 4: Target race distance shaped long run threshold>"
    ],
    "ai_personalization_additions": "<Summary of how the AI tailored instructions beyond the rigid rule baseline>"
  }
}
Return ONLY pure JSON.
"""

    return f"Structured Training Input:\n{json.dumps(payload, indent=2)}\n\n{instructions}"
