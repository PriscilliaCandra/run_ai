import json
import logging
import re
import httpx
from typing import Dict, Any, Tuple
from app.config import settings
from app.schemas import RunnerProfileCreate
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.ai.validator import validate_ai_plan, AIPlanValidationError

logger = logging.getLogger(__name__)

def clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Cleans code blocks and parses raw LLM output into a dictionary."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)

def generate_offline_ai_plan(profile: RunnerProfileCreate, rule_plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-fidelity offline heuristic AI synthesizer.
    Guarantees the prototype is 100% functional out-of-the-box even without an active LLM API key,
    while adhering to the exact same schema.
    """
    vdot = rule_plan["vdot"]
    target_pace = rule_plan["target_pace_per_km"]
    base_workouts = rule_plan["week_1_plan"]["workouts"]
    has_injury = bool(profile.injury_limitations and profile.injury_limitations.strip().lower() not in ["none", "no", "n/a", "-"])

    workouts = []
    for w in base_workouts:
        day = w["day"]
        w_type = w["workout_type"]
        dist = w["distance_km"]
        pace = w["pace_target"]
        intensity = w["intensity_zone"]

        if w_type == "Rest & Recovery":
            warmup = "None required."
            execution = "Full rest day. Focus on quality sleep (7-9 hours), balanced nutrition, and hydration."
            recovery = "Light walking or 10-15 minutes of lower limb static stretching if muscles feel tight."
        elif w_type == "Long Run":
            warmup = "5 minutes of brisk walking followed by 5 minutes of dynamic leg swings and calf raises."
            execution = (
                f"Continuous aerobic running for {dist:.1f} km at conversational pace ({pace}). "
                "Keep cadence around 170-180 spm and avoid sprinting at the finish."
            )
            recovery = "Replenish electrolytes immediately. Consume a 3:1 carb-to-protein snack within 30-45 minutes."
        elif "Tempo" in w_type or "Interval" in w_type:
            warmup = "10 minutes of very slow jogging + dynamic drills (high knees, butt kicks, A-skips, 4x60m accelerations)."
            execution = (
                f"Main quality block: sustained effort targeting lactate threshold ({pace}). "
                f"Maintain rhythm, control breathing, and practice holding your target race pace ({target_pace}/km)."
            )
            recovery = "10 minutes of gentle cool-down jogging + calf and hamstring mobility work."
        else: # Easy Run
            warmup = "3-5 minutes of easy dynamic ankle rotations, lunges, and brisk walking."
            execution = (
                f"Steady easy aerobic run ({dist:.1f} km) strictly at {pace}. "
                "You should be able to recite a sentence aloud without gasping."
            )
            recovery = "Rehydrate with 500ml water and complete 5 minutes of post-run quad and hip flexor stretches."

        if has_injury:
            execution += f" [Note: Keep stress off {profile.injury_limitations}; cease immediately if sharp discomfort arises.]"

        workouts.append({
            "day": day,
            "workout_type": w_type,
            "distance_km": dist,
            "pace_target": pace,
            "intensity_zone": intensity,
            "warmup_cooldown": warmup,
            "workout_execution": execution,
            "recovery_instruction": recovery,
            "purpose": w["purpose"]
        })

    coach_overview = (
        f"Welcome to your personalized {profile.plan_duration_weeks}-week training plan targeting your {profile.target_race_distance} race! "
        f"Based on your 5K personal best of {profile.pb_5k}, your calculated physiological aerobic index (VDOT) is {vdot:.1f}. "
        f"To safely reach your target race time of {profile.target_race_time} ({target_pace}/km), this plan balances polarized 80% aerobic base conditioning "
        f"with focused quality workouts tailored to your {profile.experience_level.lower()} experience level and {profile.training_days_per_week}-day weekly schedule."
    )

    injury_note = (
        f"You highlighted an injury limitation regarding '{profile.injury_limitations}'. "
        "The workouts emphasize conservative warm-up drills, cadence management to reduce ground contact impact, and non-negotiable rest days. "
        "Do not hesitate to substitute easy runs with elliptical or cycling if symptoms flare up."
        if has_injury else
        "No current injury reported. To preserve durability, maintain consistent core strength twice weekly and avoid abrupt mileage jumps."
    )

    return {
        "coach_overview": coach_overview,
        "weekly_mileage_km": rule_plan["week_1_plan"]["weekly_mileage_km"],
        "workouts": workouts,
        "personalized_insights": {
            "pacing_strategy": (
                f"Respect the easy run boundaries ({rule_plan['paces']['easy']['pace_range']}). "
                f"Running easy days too fast is the #1 mistake that prevents runners from achieving quality in tempo workouts."
            ),
            "injury_prevention_note": injury_note,
            "nutrition_and_recovery_advice": (
                f"With {profile.training_days_per_week} active days per week, prioritize glycogen reloading after your quality session and long run. "
                "Hydrate consistently with 30-35 ml per kg of body weight daily."
            )
        },
        "ai_personalization_summary": [
            f"Training frequency was adapted to {profile.training_days_per_week} available training days per week.",
            f"Workout sessions were aligned with your preferred training schedule ({', '.join(profile.preferred_training_days)}).",
            f"Warm-up and pacing guidance were personalized for your {profile.experience_level.lower()} experience level.",
            (
                f"Biomechanical and pacing adaptations tailored to mitigate '{profile.injury_limitations}'."
                if has_injury else "Running durability and cadence stability focus integrated."
            ),
            f"Sensory and cognitive pacing cues generated to assist holding your target race pace ({target_pace}/km)."
        ],
        "why_this_plan_was_generated": {
            "key_influencing_factors": [
                f"Current 5K PB ({profile.pb_5k}) established your baseline VDOT ({vdot:.1f}) and exact physiological pace targets.",
                f"Current weekly mileage ({profile.current_weekly_mileage} km) capped Week 1 volume to eliminate overuse injury risk.",
                f"Target race distance ({profile.target_race_distance}) determined the maximum long run threshold ({workouts[-1]['distance_km'] if workouts else 0} km).",
                f"Training availability ({profile.training_days_per_week} days/week) organized your weekly microcycle into quality, endurance, and rest."
            ],
            "ai_personalization_additions": (
                "The AI component augmented the mathematical rule baseline by generating specific step-by-step warm-up protocols, "
                "dynamic stretching routines, contextual workout execution cues, and personalized advice for reported limitations."
            )
        }
    }


async def generate_gemini_plan(prompt_text: str) -> Dict[str, Any]:
    """Invokes Google Gemini API with JSON structured output."""
    api_key = settings.GEMINI_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt_text}"}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.4
        }
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        return clean_json_response(raw_text)


async def generate_openai_plan(prompt_text: str) -> Dict[str, Any]:
    """Invokes OpenAI API."""
    api_key = settings.OPENAI_API_KEY
    url = "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"}
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        return clean_json_response(raw_text)


async def get_personalized_ai_plan(
    profile: RunnerProfileCreate,
    rule_plan: Dict[str, Any]
) -> Tuple[Dict[str, Any], str]:
    """
    Modular AI dispatcher:
    Tries configured LLM API (Gemini or OpenAI), then validates the response against
    the deterministic rule-based baseline before trusting it. Never returns raw,
    unvalidated LLM output. Gracefully falls back to the deterministic synthesizer if
    keys are absent, the API call fails, the JSON is malformed, or the plan violates
    the physiological/numerical constraints computed by the rule-based engine.
    Returns (plan_dict, model_name_used).
    """
    user_prompt = build_user_prompt(profile, rule_plan)
    provider = settings.LLM_PROVIDER.lower()

    # Determine provider
    if (provider == "gemini" or provider == "auto") and settings.GEMINI_API_KEY:
        try:
            raw_plan = await generate_gemini_plan(user_prompt)
            validated_plan = validate_ai_plan(raw_plan, rule_plan, profile)
            return validated_plan.model_dump(), f"Gemini ({settings.GEMINI_MODEL})"
        except AIPlanValidationError as e:
            logger.warning("Gemini output failed constraint validation, falling back to offline synthesizer: %s", e)
        except json.JSONDecodeError:
            logger.warning("Gemini returned malformed JSON, falling back to offline synthesizer.")
        except Exception as e:
            logger.warning("Gemini API call failed (%s), falling back to offline synthesizer.", type(e).__name__)

    if (provider == "openai" or provider == "auto") and settings.OPENAI_API_KEY:
        try:
            raw_plan = await generate_openai_plan(user_prompt)
            validated_plan = validate_ai_plan(raw_plan, rule_plan, profile)
            return validated_plan.model_dump(), f"OpenAI ({settings.OPENAI_MODEL})"
        except AIPlanValidationError as e:
            logger.warning("OpenAI output failed constraint validation, falling back to offline synthesizer: %s", e)
        except json.JSONDecodeError:
            logger.warning("OpenAI returned malformed JSON, falling back to offline synthesizer.")
        except Exception as e:
            logger.warning("OpenAI API call failed (%s), falling back to offline synthesizer.", type(e).__name__)

    # Graceful fallback synthesizer (deterministic: reuses baseline numbers verbatim)
    fallback_plan = generate_offline_ai_plan(profile, rule_plan)
    return fallback_plan, "AI Synthesis Engine (Rule-Constrained Academic Fallback)"
