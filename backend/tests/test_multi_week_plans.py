"""
Phase 5 multi-week training plan coverage:
- Multi-week deterministic rule generation (4w, 8w, 24w)
- Full-plan materialization (N * 7 rows, unique on plan_id, week_number, day_of_week)
- Scheduled date calculation across multiple weeks and start-date weekdays
- Dashboard current-week derivation (before start, active, after end)
- Workout linking into non-Week-1 scheduled workouts
- Legacy Week-1-only plan compatibility
- Anonymous research plan zero-row isolation
"""
from datetime import date, timedelta
import pytest

from app.rules.generator import generate_rule_based_plan, DAYS_OF_WEEK
from app.schemas import RunnerProfileCreate
from app.workouts.service import scheduled_date_for, materialize_training_plan_workouts
from tests.factories import make_profile_payload, make_workout_payload, register_and_login


def _make_profile(duration_weeks: int = 8, **kwargs) -> RunnerProfileCreate:
    payload = make_profile_payload(plan_duration_weeks=duration_weeks, **kwargs)
    return RunnerProfileCreate(**payload)


# --- 1. Multi-Week Generation ---

@pytest.mark.parametrize("duration", [4, 8, 12, 16, 24])
def test_rule_engine_generates_all_weeks(duration):
    profile = _make_profile(duration_weeks=duration)
    plan = generate_rule_based_plan(profile)

    assert "weeks" in plan
    assert len(plan["weeks"]) == duration
    assert len(plan["progression_schedule"]) == duration

    for i, week in enumerate(plan["weeks"], start=1):
        assert week["week_number"] == i
        assert len(week["workouts"]) == 7
        assert week["weekly_mileage_km"] > 0
        days = [w["day"] for w in week["workouts"]]
        assert days == DAYS_OF_WEEK


def test_weekly_mileage_scales_workout_distances():
    profile = _make_profile(duration_weeks=8, current_weekly_mileage=20.0)
    plan = generate_rule_based_plan(profile)

    weeks = plan["weeks"]
    # Week 1 vs progressive build week vs cutback week vs taper week
    w1_long_run = next(w for w in weeks[0]["workouts"] if "long" in w["workout_type"].lower())
    w3_long_run = next(w for w in weeks[2]["workouts"] if "long" in w["workout_type"].lower())

    # Build week should have longer long run than week 1
    assert w3_long_run["distance_km"] >= w1_long_run["distance_km"]

    # Deload week (week 4) has reduced target mileage
    w4 = weeks[3]
    assert w4["phase"] == "Recovery Cutback Week"
    assert w4["weekly_mileage_km"] < weeks[2]["weekly_mileage_km"]


# --- 2. Materialization ---

@pytest.mark.parametrize("duration", [4, 8, 24])
def test_consumer_plan_materializes_exact_row_count(client, duration):
    register_and_login(client, email=f"user-mat-{duration}@example.com")
    res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=duration))
    assert res.status_code == 201
    plan_id = res.json()["plan_id"]

    workouts_res = client.get(f"/api/plans/{plan_id}/workouts")
    assert workouts_res.status_code == 200
    workouts = workouts_res.json()

    assert len(workouts) == duration * 7
    week_nums = {w["week_number"] for w in workouts}
    assert week_nums == set(range(1, duration + 1))

    # Verify no duplicate (week_number, day_of_week)
    keys = {(w["week_number"], w["day_of_week"]) for w in workouts}
    assert len(keys) == duration * 7


# --- 3. Scheduled Dates ---

def test_scheduled_date_for_multi_week_offsets():
    start_monday = date(2026, 9, 28)  # Monday
    # Week 1 Monday
    assert scheduled_date_for(start_monday, 1, "Monday") == date(2026, 9, 28)
    # Week 1 Sunday
    assert scheduled_date_for(start_monday, 1, "Sunday") == date(2026, 10, 4)
    # Week 2 Monday = Week 1 + 7 days
    assert scheduled_date_for(start_monday, 2, "Monday") == date(2026, 10, 5)
    # Week 3 Wednesday = Week 1 + 14 days + 2 days
    assert scheduled_date_for(start_monday, 3, "Wednesday") == date(2026, 10, 14)
    # Week 8 Sunday
    assert scheduled_date_for(start_monday, 8, "Sunday") == date(2026, 11, 22)


def test_scheduled_date_for_midweek_and_sunday_starts():
    start_wed = date(2026, 9, 30)  # Wednesday
    # Week 1 Wed
    assert scheduled_date_for(start_wed, 1, "Wednesday") == date(2026, 9, 30)
    # Week 1 Mon (wraps to next Monday)
    assert scheduled_date_for(start_wed, 1, "Monday") == date(2026, 10, 5)
    # Week 2 Wed
    assert scheduled_date_for(start_wed, 2, "Wednesday") == date(2026, 10, 7)
    # Week 2 Mon
    assert scheduled_date_for(start_wed, 2, "Monday") == date(2026, 10, 12)

    start_sun = date(2026, 10, 4)  # Sunday
    # Week 1 Sun
    assert scheduled_date_for(start_sun, 1, "Sunday") == date(2026, 10, 4)
    # Week 1 Mon
    assert scheduled_date_for(start_sun, 1, "Monday") == date(2026, 10, 5)
    # Week 3 Sun
    assert scheduled_date_for(start_sun, 3, "Sunday") == date(2026, 10, 18)


# --- 4. Dashboard Current Week Handling ---

def test_dashboard_current_week_tracking_across_weeks(client):
    register_and_login(client)
    plan_res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=8))
    plan_id = plan_res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlan

    # Simulate Week 3
    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        plan.start_date = date.today() - timedelta(days=14)  # Day 15 -> Week 3
        db.commit()
    finally:
        db.close()

    res = client.get("/api/dashboard/summary")
    active = res.json()["active_plan"]
    assert active["current_week"] == 3
    assert active["current_week_detail_available"] is True
    assert active["today_scheduled_workout"] is not None
    assert active["today_scheduled_workout"]["week_number"] == 3
    assert active["today_scheduled_workout"]["day_of_week"] == date.today().strftime("%A")


def test_dashboard_before_start_and_after_end(client):
    register_and_login(client)
    plan_res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=8))
    plan_id = plan_res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlan

    # Before start (start_date in future)
    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        plan.start_date = date.today() + timedelta(days=3)
        db.commit()
    finally:
        db.close()

    res = client.get("/api/dashboard/summary")
    active = res.json()["active_plan"]
    assert active["current_week"] == 1
    assert active["current_week_detail_available"] is True

    # After end (start_date 60 days ago for 8-week / 56-day plan)
    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        plan.start_date = date.today() - timedelta(days=60)
        db.commit()
    finally:
        db.close()

    res_after = client.get("/api/dashboard/summary")
    active_after = res_after.json()["active_plan"]
    assert active_after["current_week"] == 8
    assert active_after["current_week_detail_available"] is False
    assert active_after["today_scheduled_workout"] is None


# --- 5. Linking to Non-Week-1 Workouts ---

def test_link_workout_to_week_three_scheduled_workout(client):
    register_and_login(client)
    plan_res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=8))
    plan_id = plan_res.json()["plan_id"]

    # Fetch workouts and find a loggable week 3 workout
    workouts = client.get(f"/api/plans/{plan_id}/workouts").json()
    week3_loggable = [w for w in workouts if w["week_number"] == 3 and w["completion_status"] is not None]
    assert len(week3_loggable) > 0
    target_tpw = week3_loggable[0]

    # Log a workout linking to week 3
    log_res = client.post("/api/workouts", json=make_workout_payload(
        training_plan_workout_id=target_tpw["id"],
        distance_meters=target_tpw["distance_meters"],
        duration_seconds=1800,
    ))
    assert log_res.status_code == 201
    log_body = log_res.json()
    assert log_body["linked_scheduled_workout"] is not None
    assert log_body["linked_scheduled_workout"]["id"] == target_tpw["id"]
    assert log_body["linked_scheduled_workout"]["week_number"] == 3

    # Verify plan workouts endpoint reflects completed status
    updated_workouts = client.get(f"/api/plans/{plan_id}/workouts").json()
    updated_tpw = next(w for w in updated_workouts if w["id"] == target_tpw["id"])
    assert updated_tpw["completion_status"] == "completed"
    assert len(updated_tpw["linked_workout_logs"]) == 1


# --- 6. Legacy Week-1 Plan Compatibility ---

def test_legacy_week_one_only_plan_compatibility(client):
    register_and_login(client)
    # Generate plan and simulate legacy state by deleting weeks > 1
    plan_res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=8))
    plan_id = plan_res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlanWorkout

    db = SessionLocal()
    try:
        db.query(TrainingPlanWorkout).filter(
            TrainingPlanWorkout.training_plan_id == plan_id,
            TrainingPlanWorkout.week_number > 1
        ).delete()
        db.commit()
    finally:
        db.close()

    # Verify workouts endpoint returns exactly week 1
    workouts = client.get(f"/api/plans/{plan_id}/workouts").json()
    assert len(workouts) == 7
    assert all(w["week_number"] == 1 for w in workouts)

    # Verify plan detail endpoint opens fine
    detail = client.get(f"/api/plans/{plan_id}").json()
    assert detail["plan_id"] == plan_id


# --- 7. Research Plan Isolation ---

def test_anonymous_multi_week_research_plan_has_zero_workouts(client):
    # Unauthenticated research plan with 16 weeks
    res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=16))
    assert res.status_code == 201
    plan_id = res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlanWorkout, TrainingPlan

    db = SessionLocal()
    try:
        count = db.query(TrainingPlanWorkout).filter(TrainingPlanWorkout.training_plan_id == plan_id).count()
        assert count == 0
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert plan.user_id is None
        assert plan.start_date is None
        assert plan.status is None
    finally:
        db.close()

    # Research evaluation works
    eval_res = client.post("/api/evaluations", json={
        "training_plan_id": plan_id,
        "evaluated_plan_type": "ai_personalized",
        "personalization_score": 5,
        "usefulness_score": 4,
        "clarity_score": 5,
        "confidence_score": 4,
        "comments": "Great research plan.",
    })
    assert eval_res.status_code == 201

    stats_res = client.get("/api/evaluations/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["total_evaluations"] >= 1
