"""
Rule engine coverage: VDOT/pace calculation, training-day distribution across
1-7 days/week, the weekly-mileage baseline constraint, the long-run volume
heuristic, and the safe weekly progression cap.
"""
import pytest

from app.rules.generator import generate_rule_based_plan
from app.rules.vdot import calculate_vdot_from_race, calculate_training_paces
from tests.factories import make_profile

PREFERRED_DAYS_BY_COUNT = {
    1: ["Sunday"],
    2: ["Tuesday", "Sunday"],
    3: ["Tuesday", "Thursday", "Sunday"],
    4: ["Tuesday", "Thursday", "Saturday", "Sunday"],
    5: ["Monday", "Tuesday", "Thursday", "Saturday", "Sunday"],
    6: ["Monday", "Tuesday", "Wednesday", "Thursday", "Saturday", "Sunday"],
    7: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


def test_vdot_formula_matches_known_reference_value():
    # 5K in 24:56 = 1496 seconds -> VDOT ~38.4 (Daniels-Gilbert reference table)
    vdot = calculate_vdot_from_race(5000.0, 1496.0)
    assert 37.0 <= vdot <= 40.0

    paces = calculate_training_paces(vdot)
    assert "easy" in paces and "threshold" in paces and "interval" in paces


def test_valid_profile_produces_a_complete_plan():
    profile = make_profile()
    plan = generate_rule_based_plan(profile)

    assert plan["vdot"] > 0
    assert len(plan["week_1_plan"]["workouts"]) == 7
    assert len(plan["progression_schedule"]) == profile.plan_duration_weeks
    assert "explainability" in plan


@pytest.mark.parametrize("days_count", range(1, 8))
def test_training_day_distribution_across_all_valid_day_counts(days_count):
    profile = make_profile(
        training_days_per_week=days_count,
        preferred_training_days=PREFERRED_DAYS_BY_COUNT[days_count],
    )
    plan = generate_rule_based_plan(profile)
    workouts = plan["week_1_plan"]["workouts"]

    assert len(workouts) == 7, "every plan always has one entry per calendar day"

    active = [w for w in workouts if w["workout_type"] != "Rest & Recovery"]
    rest = [w for w in workouts if w["workout_type"] == "Rest & Recovery"]

    assert len(active) == days_count
    assert len(rest) == 7 - days_count
    assert all(w["distance_km"] > 0 for w in active)
    assert all(w["distance_km"] == 0.0 for w in rest)

    if days_count == 1:
        # Historically crashed: with only one active day there is no second
        # day to host a separate quality session (see generator.py).
        assert active[0]["workout_type"] == "Long Run"


def test_single_training_day_preserves_injury_guidance():
    profile = make_profile(
        training_days_per_week=1,
        preferred_training_days=["Sunday"],
        injury_limitations="Mild Achilles tightness",
    )
    plan = generate_rule_based_plan(profile)
    active = [w for w in plan["week_1_plan"]["workouts"] if w["workout_type"] != "Rest & Recovery"]
    assert len(active) == 1
    assert "Achilles" in active[0]["recovery_instruction"]


def test_week_one_mileage_tracks_current_capacity():
    """Week 1 volume should closely match current_weekly_mileage (no acute spike)."""
    profile = make_profile(current_weekly_mileage=25.0, training_days_per_week=4)
    plan = generate_rule_based_plan(profile)
    assert abs(plan["week_1_plan"]["weekly_mileage_km"] - 25.0) <= 2.0


def test_long_run_respects_the_thirty_percent_design_heuristic():
    """
    At a mid-range weekly volume (where neither the 4km floor nor the
    per-distance ceiling kick in), the long run should sit at ~30% of the
    week's total volume, per the prototype's polarized-training design.
    """
    profile = make_profile(current_weekly_mileage=30.0, target_race_distance="5K")
    plan = generate_rule_based_plan(profile)
    weekly_mileage = plan["week_1_plan"]["weekly_mileage_km"]
    long_run = next(w for w in plan["week_1_plan"]["workouts"] if w["workout_type"] == "Long Run")

    assert long_run["distance_km"] <= round(weekly_mileage * 0.30, 1) + 0.1


def test_weekly_progression_never_exceeds_the_safe_increment():
    """Consecutive 'Progressive Build Phase' weeks must not jump by more than ~10%."""
    profile = make_profile(current_weekly_mileage=25.0, plan_duration_weeks=8)
    plan = generate_rule_based_plan(profile)
    progression = plan["progression_schedule"]

    for prev, curr in zip(progression, progression[1:]):
        if prev["phase"] == "Progressive Build Phase" and curr["phase"] == "Progressive Build Phase":
            increase_pct = (curr["target_mileage_km"] - prev["target_mileage_km"]) / prev["target_mileage_km"]
            assert increase_pct <= 0.10 + 1e-6, (
                f"week-over-week increase of {increase_pct:.1%} exceeds the ~10% safe progression cap"
            )
