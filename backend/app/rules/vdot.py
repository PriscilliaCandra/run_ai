import math
from typing import Dict, Tuple
from app.schemas import parse_time_to_seconds, format_seconds_to_pace

def calculate_vdot_from_race(distance_meters: float, time_seconds: float) -> float:
    """
    Calculates Jack Daniels VDOT based on race distance (meters) and finish time (seconds).
    Uses the Daniels-Gilbert formula.
    """
    time_minutes = time_seconds / 60.0
    velocity_m_per_min = distance_meters / time_minutes

    # VO2 cost at velocity v (ml/kg/min)
    vo2 = -4.60 + (0.182258 * velocity_m_per_min) + (0.000104 * (velocity_m_per_min ** 2))

    # Fraction of VO2max sustainable for duration t
    fraction_vo2max = (
        0.8
        + (0.1894393 * math.exp(-0.012778 * time_minutes))
        + (0.2989558 * math.exp(-0.1932605 * time_minutes))
    )

    if fraction_vo2max <= 0:
        fraction_vo2max = 0.8

    vdot = vo2 / fraction_vo2max
    return round(vdot, 2)

def velocity_from_vo2(target_vo2: float) -> float:
    """
    Solves the quadratic equation:
    0.000104*v^2 + 0.182258*v - (4.60 + target_vo2) = 0
    Returns velocity in meters per minute.
    """
    a = 0.000104
    b = 0.182258
    c = -(4.60 + target_vo2)
    discriminant = (b ** 2) - (4 * a * c)
    if discriminant < 0:
        return 150.0  # reasonable fallback
    v = (-b + math.sqrt(discriminant)) / (2 * a)
    return max(v, 60.0)

def pace_from_velocity(v_m_per_min: float) -> int:
    """Converts velocity (m/min) to seconds per kilometer."""
    if v_m_per_min <= 0:
        return 600
    sec_per_km = (1000.0 / v_m_per_min) * 60.0
    return int(round(sec_per_km))

def calculate_training_paces(vdot: float) -> Dict[str, Dict[str, str]]:
    """
    Calculates standard Jack Daniels training zones based on VDOT:
    - Easy (E): ~65-74% VO2max
    - Marathon / Steady (M): ~80% VO2max
    - Threshold / Tempo (T): ~88% VO2max
    - Interval (I): ~98% VO2max
    - Repetition (R): ~105% VO2max
    """
    # Easy pace range
    v_easy_slow = velocity_from_vo2(vdot * 0.65)
    v_easy_fast = velocity_from_vo2(vdot * 0.74)
    sec_easy_slow = pace_from_velocity(v_easy_slow)
    sec_easy_fast = pace_from_velocity(v_easy_fast)

    # Marathon / Steady
    v_marathon = velocity_from_vo2(vdot * 0.80)
    sec_marathon = pace_from_velocity(v_marathon)

    # Threshold / Tempo
    v_threshold = velocity_from_vo2(vdot * 0.88)
    sec_threshold = pace_from_velocity(v_threshold)

    # Interval (VO2max)
    v_interval = velocity_from_vo2(vdot * 0.98)
    sec_interval = pace_from_velocity(v_interval)

    # Repetition (Speed)
    v_rep = velocity_from_vo2(vdot * 1.05)
    sec_rep = pace_from_velocity(v_rep)

    return {
        "easy": {
            "pace_range": f"{format_seconds_to_pace(sec_easy_fast)} - {format_seconds_to_pace(sec_easy_slow)} /km",
            "intensity": "Zone 2 (65-74% VO2max, Conversational)",
            "purpose": "Build aerobic endurance, vascularization, and recovery without systemic fatigue."
        },
        "marathon": {
            "pace_range": f"{format_seconds_to_pace(sec_marathon)} /km",
            "intensity": "Zone 3 (80% VO2max, Steady Aerobic)",
            "purpose": "Improve muscular glycogen storage and race-specific aerobic efficiency."
        },
        "threshold": {
            "pace_range": f"{format_seconds_to_pace(sec_threshold)} /km",
            "intensity": "Zone 4 (88% VO2max, Comfortably Hard)",
            "purpose": "Raise lactate clearance threshold to sustain high speeds with less fatigue."
        },
        "interval": {
            "pace_range": f"{format_seconds_to_pace(sec_interval)} /km",
            "intensity": "Zone 5 (98% VO2max, Hard / VO2max)",
            "purpose": "Expand maximum aerobic capacity (VO2max) and cardiac stroke volume."
        },
        "repetition": {
            "pace_range": f"{format_seconds_to_pace(sec_rep)} /km",
            "intensity": "Anaerobic (105% VO2max, Very Fast)",
            "purpose": "Improve running economy, neuromuscular coordination, and biomechanical power."
        }
    }

def get_distance_meters(race_name: str) -> float:
    mapping = {
        "5k": 5000.0,
        "10k": 10000.0,
        "half marathon": 21097.5,
    }
    return mapping.get(race_name.strip().lower(), 5000.0)

def calculate_target_pace(distance_str: str, target_time_str: str) -> Tuple[str, int]:
    """Calculates target race pace in MM:SS per km and in seconds."""
    dist_meters = get_distance_meters(distance_str)
    dist_km = dist_meters / 1000.0
    total_seconds = parse_time_to_seconds(target_time_str)
    sec_per_km = int(round(total_seconds / dist_km))
    return format_seconds_to_pace(sec_per_km), sec_per_km
