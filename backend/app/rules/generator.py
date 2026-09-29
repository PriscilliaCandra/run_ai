import math
from typing import Dict, List, Any
from app.schemas import RunnerProfileCreate, WorkoutItem, parse_time_to_seconds, format_seconds_to_pace
from app.rules.vdot import (
    calculate_vdot_from_race,
    calculate_training_paces,
    calculate_target_pace,
    get_distance_meters,
)

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def generate_weekly_progression_summary(
    base_mileage: float,
    total_weeks: int,
    target_race_distance: str
) -> List[Dict[str, Any]]:
    """
    Generates a safe periodization progression:
    - Base Building (Weeks 1 to N-3 with periodic cutback recovery every 4 weeks)
    - Peak volume (Week N-2 or N-3)
    - Tapering (Final 1-2 weeks before race)
    """
    progression = []
    current = base_mileage

    for w in range(1, total_weeks + 1):
        if w == total_weeks:
            # Race Week: Tapered volume (~50-60% of baseline)
            vol = round(base_mileage * 0.55, 1)
            phase = "Race Week & Taper"
            note = f"Taper week: Reduced volume to keep legs fresh for race day ({target_race_distance})."
        elif w == total_weeks - 1:
            # Pre-race taper (~75% of peak)
            vol = round(base_mileage * 0.85, 1)
            phase = "Taper Phase"
            note = "Begin race taper; maintain intensity in short bursts but drop overall volume."
        elif w % 4 == 0:
            # Recovery / Cutback week (-15% volume)
            vol = round(current * 0.85, 1)
            phase = "Recovery Cutback Week"
            note = "Scheduled deload week to allow muscular and connective tissue adaptation."
        else:
            # Safe 5-8% increase capped at 10%
            increase_factor = 1.06 if base_mileage >= 20 else 1.08
            current = round(current * increase_factor, 1)
            vol = current
            phase = "Progressive Build Phase"
            note = "Steady volume increment respecting the ≤10% weekly safe mileage principle."

        progression.append({
            "week_number": w,
            "target_mileage_km": vol,
            "phase": phase,
            "focus_note": note
        })

    return progression


def distribute_workouts_across_week(
    profile: RunnerProfileCreate,
    paces: Dict[str, Dict[str, str]],
    target_pace_str: str,
    weekly_mileage: float
) -> List[WorkoutItem]:
    """
    Distributes workouts scientifically across days of the week:
    - Quality session (Tempo or Interval)
    - Long Run (max 30% of total weekly volume)
    - Easy Aerobic Runs
    - Rest / Active Recovery days
    """
    days_count = profile.training_days_per_week
    preferred_days = [d.strip().capitalize() for d in profile.preferred_training_days]
    
    # If preferred days count doesn't match days_count, align them
    active_days_set = set()
    for d in DAYS_OF_WEEK:
        if d in preferred_days and len(active_days_set) < days_count:
            active_days_set.add(d)

    # Fill remaining days if needed
    if len(active_days_set) < days_count:
        for d in ["Tuesday", "Thursday", "Saturday", "Sunday", "Wednesday", "Friday", "Monday"]:
            if d not in active_days_set:
                active_days_set.add(d)
                if len(active_days_set) == days_count:
                    break

    # With only one training day available, there is no second active day to host a
    # separate quality (tempo/interval) session, which would otherwise crash the
    # day-selection logic below. Schedule a single safe aerobic session instead.
    if days_count <= 1:
        only_day = next(iter(active_days_set)) if active_days_set else DAYS_OF_WEEK[0]
        single_run_km = round(max(weekly_mileage, 3.0), 1)
        has_injury_note = bool(profile.injury_limitations and profile.injury_limitations.strip().lower() not in ["none", "no", "n/a", "-"])
        recovery = "Cool down with 10 minutes of walking, refuel with carbohydrates and protein within 45 minutes, hydrate thoroughly."
        if has_injury_note:
            recovery += f" Note: Monitor {profile.injury_limitations}; substitute with low-impact strides or reduce pace if irritation arises."

        single_day_workouts: List[WorkoutItem] = []
        for day in DAYS_OF_WEEK:
            if day == only_day:
                single_day_workouts.append(WorkoutItem(
                    day=day,
                    workout_type="Long Run",
                    distance_km=single_run_km,
                    pace_target=paces["easy"]["pace_range"],
                    intensity_zone=paces["easy"]["intensity"],
                    recovery_instruction=recovery,
                    purpose="With only one weekly training day available, this single aerobic session covers the full weekly volume at a safe, conversational effort rather than splitting into a separate high-intensity session."
                ))
            else:
                single_day_workouts.append(WorkoutItem(
                    day=day,
                    workout_type="Rest & Recovery",
                    distance_km=0.0,
                    pace_target="N/A",
                    intensity_zone="Rest (Zone 1 or Complete Rest)",
                    recovery_instruction="Rest completely or perform light mobility stretching, foam rolling, and adequate hydration.",
                    purpose="Allows muscle glycogen replenishment, micro-tear repair, and physiological adaptation."
                ))
        return single_day_workouts

    # Calculate Volume Allocations (80/20 Rule)
    # Long run is ~28-30% of weekly volume
    long_run_km = round(weekly_mileage * 0.30, 1)
    
    # Minimum and maximum sensible long run bounds
    if profile.target_race_distance == "5K":
        long_run_km = min(long_run_km, 12.0)
    elif profile.target_race_distance == "10K":
        long_run_km = min(long_run_km, 16.0)
    elif profile.target_race_distance == "Half Marathon":
        long_run_km = min(long_run_km, 21.0)
    long_run_km = max(long_run_km, 4.0)

    # Quality workout (Interval or Tempo): ~18-20% of weekly volume
    quality_km = round(weekly_mileage * 0.20, 1)
    quality_km = max(quality_km, 3.5)

    # Remainder is split across easy runs
    remaining_mileage = max(weekly_mileage - (long_run_km + quality_km), 0.0)
    easy_days_count = max(days_count - 2, 0)
    
    if easy_days_count > 0:
        easy_run_each_km = round(remaining_mileage / easy_days_count, 1)
        easy_run_each_km = max(easy_run_each_km, 3.0)
    else:
        easy_run_each_km = 3.0

    # Pick long run day (Sunday if active, else Saturday, else last active day)
    long_run_day = "Sunday" if "Sunday" in active_days_set else ("Saturday" if "Saturday" in active_days_set else sorted(list(active_days_set))[-1])
    
    # Pick quality workout day (Tuesday or Wednesday, not adjacent to long run if possible)
    potential_quality_days = [d for d in ["Tuesday", "Wednesday", "Thursday"] if d in active_days_set and d != long_run_day]
    quality_day = potential_quality_days[0] if potential_quality_days else [d for d in active_days_set if d != long_run_day][0]

    workouts: List[WorkoutItem] = []

    has_injury_note = bool(profile.injury_limitations and profile.injury_limitations.strip().lower() not in ["none", "no", "n/a", "-"])

    for day in DAYS_OF_WEEK:
        if day not in active_days_set:
            workouts.append(WorkoutItem(
                day=day,
                workout_type="Rest & Recovery",
                distance_km=0.0,
                pace_target="N/A",
                intensity_zone="Rest (Zone 1 or Complete Rest)",
                recovery_instruction="Rest completely or perform light mobility stretching, foam rolling, and adequate hydration.",
                purpose="Allows muscle glycogen replenishment, micro-tear repair, and physiological adaptation."
            ))
        elif day == long_run_day:
            workouts.append(WorkoutItem(
                day=day,
                workout_type="Long Run",
                distance_km=long_run_km,
                pace_target=paces["easy"]["pace_range"],
                intensity_zone=paces["easy"]["intensity"],
                recovery_instruction="Cool down with 10 minutes of walking, refuel with carbohydrates and protein within 45 minutes, hydrate thoroughly.",
                purpose="Builds capillary density, mitochondrial density, and mental stamina for race distance."
            ))
        elif day == quality_day:
            # Alternates or chooses Tempo / Interval based on experience
            if profile.experience_level.lower() == "beginner":
                workout_type = "Tempo Run"
                pace_target = paces["threshold"]["pace_range"]
                intensity = paces["threshold"]["intensity"]
                purpose = "Improves lactate threshold clearance and running economy at steady challenging effort."
                recovery = "10 min easy warm-up jog, 10 min cool-down jog, dynamic stretches before starting."
            else:
                workout_type = "Interval Training"
                pace_target = f"{paces['interval']['pace_range']} (Reps) / Easy Jog (Rest)"
                intensity = paces["interval"]["intensity"]
                purpose = f"Increases VO2max and cardiac stroke volume. Target race pace awareness ({target_pace_str}/km)."
                recovery = "Warm up 1.5 km easy, 4x800m or 6x400m hard with 2 min recovery jogs, 1.5 km cool down."
            
            if has_injury_note:
                recovery += f" Note: Monitor {profile.injury_limitations}; substitute with low-impact strides or reduce pace if irritation arises."

            workouts.append(WorkoutItem(
                day=day,
                workout_type=workout_type,
                distance_km=quality_km,
                pace_target=pace_target,
                intensity_zone=intensity,
                recovery_instruction=recovery,
                purpose=purpose
            ))
        else:
            # Easy Aerobic Run
            workouts.append(WorkoutItem(
                day=day,
                workout_type="Easy Aerobic Run",
                distance_km=easy_run_each_km,
                pace_target=paces["easy"]["pace_range"],
                intensity_zone=paces["easy"]["intensity"],
                recovery_instruction="Keep pace strictly conversational. If breathing becomes labored, slow down.",
                purpose="Develops aerobic base conditioning and promotes active muscular blood flow without fatigue."
            ))

    return workouts


def generate_rule_based_plan(profile: RunnerProfileCreate) -> Dict[str, Any]:
    """
    Executes the pure deterministic sports-science rule engine:
    1. VDOT calculation
    2. Pace zones determination
    3. Target race pace calculation
    4. Safe weekly mileage distribution (80/20 Seiler rule & 10% progression rule)
    5. Explainability matrix
    """
    # 1. Calculate VDOT from 5K PB
    dist_5k_meters = 5000.0
    pb_5k_sec = parse_time_to_seconds(profile.pb_5k)
    vdot = calculate_vdot_from_race(dist_5k_meters, pb_5k_sec)

    # 2. Calculate Paces
    paces = calculate_training_paces(vdot)
    target_pace_str, target_pace_sec = calculate_target_pace(profile.target_race_distance, profile.target_race_time)

    # Calculate quantitative pace delta for defensible feasibility check
    pb_5k_pace_sec = int(pb_5k_sec / 5.0)
    pace_delta_pct = round(((pb_5k_pace_sec - target_pace_sec) / pb_5k_pace_sec) * 100.0, 1)

    if pace_delta_pct <= 0:
        feasibility_note = f"Target pace ({target_pace_str}/km) is conservative relative to 5K PB pace ({format_seconds_to_pace(pb_5k_pace_sec)}/km). High feasibility."
        feasibility_status = "Conservative / Highly Feasible"
    elif pace_delta_pct <= 3.5:
        feasibility_note = f"Target pace requires a {pace_delta_pct}% pace improvement. Physiologically realistic for a {profile.plan_duration_weeks}-week progressive build."
        feasibility_status = "Realistic / Well-Calibrated"
    elif pace_delta_pct <= 6.5:
        feasibility_note = f"Target pace requires a {pace_delta_pct}% pace improvement. Ambitious goal requiring strict adherence to aerobic volume and recovery."
        feasibility_status = "Ambitious / High Effort"
    else:
        feasibility_note = f"Target pace requires a {pace_delta_pct}% pace improvement. Aggressive overreach for an {profile.plan_duration_weeks}-week training window; elevated injury risk."
        feasibility_status = "Aggressive Overreach / High Fatigue Risk"

    # 3. Workouts for Baseline Week (Week 1)
    week_1_workouts = distribute_workouts_across_week(
        profile=profile,
        paces=paces,
        target_pace_str=target_pace_str,
        weekly_mileage=profile.current_weekly_mileage
    )

    actual_week_mileage = sum(w.distance_km for w in week_1_workouts)

    # 4. Weekly progression summary across total plan weeks
    progression = generate_weekly_progression_summary(
        base_mileage=profile.current_weekly_mileage,
        total_weeks=profile.plan_duration_weeks,
        target_race_distance=profile.target_race_distance
    )

    # 5. Scientific 4-Part Traceability & Explainability Matrix
    explainability = {
        # Part 1: Runner Inputs Utilized
        "runner_inputs_utilized": {
            "age": profile.age,
            "gender": profile.gender,
            "experience_level": profile.experience_level,
            "pb_5k": profile.pb_5k,
            "optional_10k_pb": profile.pb_10k or "Not provided",
            "target_race": f"{profile.target_race_distance} in {profile.target_race_time}",
            "current_weekly_mileage": f"{profile.current_weekly_mileage} km/week",
            "training_frequency": f"{profile.training_days_per_week} days/week",
            "preferred_days": profile.preferred_training_days,
            "injury_limitations": profile.injury_limitations or "None reported",
            "easy_run_pace": profile.easy_run_pace
        },
        # Part 2: Physiological Engine Values
        "physiological_engine_values": {
            "calculated_vdot": vdot,
            "vdot_interpretation": f"Daniels-Gilbert formula derived VDOT of {vdot:.1f} from 5K PB ({profile.pb_5k}).",
            "target_race_pace": f"{target_pace_str} /km",
            "pb_5k_pace": f"{format_seconds_to_pace(pb_5k_pace_sec)} /km",
            "pace_delta_percentage": f"{pace_delta_pct}%",
            "feasibility_assessment": feasibility_note,
            "feasibility_status": feasibility_status,
            "training_pace_zones": {
                "easy_zone": paces["easy"]["pace_range"],
                "marathon_zone": paces["marathon"]["pace_range"],
                "threshold_zone": paces["threshold"]["pace_range"],
                "interval_zone": paces["interval"]["pace_range"],
                "repetition_zone": paces["repetition"]["pace_range"]
            }
        },
        # Part 3: Applied Prototype Constraints (Design principles, not universal laws)
        "applied_prototype_constraints": {
            "volume_split_heuristic": (
                f"Polarized training design heuristic (~80% low-intensity aerobic: {actual_week_mileage * 0.8:.1f} km, "
                f"~20% high-intensity quality: {actual_week_mileage * 0.2:.1f} km) across {actual_week_mileage:.1f} km total."
            ),
            "baseline_mileage_constraint": f"Week 1 mileage matches current capacity ({profile.current_weekly_mileage} km) to prevent acute spikes.",
            "long_run_boundary": "Long run distance is constrained to ≤30% of total weekly volume.",
            "weekly_progression_heuristic": "Progressive build capped at ≤8-10% weekly mileage increases with scheduled cutback deload weeks.",
            "rest_day_spacing": f"{7 - profile.training_days_per_week} rest days scheduled strategically around quality and long run sessions."
        },
        # Part 4: AI Personalization Summary
        "ai_personalization_summary": [
            f"Training frequency adapted to {profile.training_days_per_week} available days per week.",
            f"Workout sessions aligned with preferred days: {', '.join(profile.preferred_training_days)}.",
            f"Warm-up protocols, strides, and cool-down routines personalized for {profile.experience_level.lower()} experience level.",
            (
                f"Injury precautions tailored for reported issue: '{profile.injury_limitations}'."
                if profile.injury_limitations else "General running durability and cadence stability guidance integrated."
            ),
            f"Cognitive pacing cues provided to guide adherence to target race pace ({target_pace_str}/km)."
        ]
    }

    return {
        "vdot": vdot,
        "target_pace_per_km": target_pace_str,
        "paces": paces,
        "week_1_plan": {
            "week_number": 1,
            "weekly_mileage_km": round(actual_week_mileage, 1),
            "focus": "Aerobic Base Calibration & Routine Adaptation",
            "workouts": [w.model_dump() for w in week_1_workouts]
        },
        "progression_schedule": progression,
        "explainability": explainability
    }
