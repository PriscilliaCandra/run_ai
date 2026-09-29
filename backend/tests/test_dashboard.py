"""
Dashboard summary coverage: authentication requirement, all four
plan/workout presence combinations, week/month date-boundary correctness,
and soft-deleted-workout exclusion.
"""
from datetime import date, timedelta

from tests.factories import make_profile_payload, make_workout_payload, register_and_login


def _create_workout(client, **overrides):
    return client.post("/api/workouts", json=make_workout_payload(**overrides))


def test_dashboard_requires_authentication(client):
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 401


def test_dashboard_empty_state_no_plan_no_workouts(client):
    register_and_login(client)
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["active_plan"] is None
    assert body["has_any_workout_history"] is False
    assert body["this_week"]["run_count"] == 0
    assert body["this_week"]["total_distance_km"] == 0
    assert body["this_week"]["average_pace_display"] is None
    assert body["recent_activities"] == []


def test_dashboard_plan_without_workouts(client):
    register_and_login(client)
    client.post("/api/plans/generate", json=make_profile_payload())

    res = client.get("/api/dashboard/summary")
    body = res.json()
    assert body["active_plan"] is not None
    assert body["active_plan"]["current_week"] == 1
    assert body["active_plan"]["current_week_detail_available"] is True
    assert body["has_any_workout_history"] is False


def test_dashboard_workouts_without_active_plan(client):
    register_and_login(client)
    _create_workout(client, distance_meters=5000, duration_seconds=1500)

    res = client.get("/api/dashboard/summary")
    body = res.json()
    assert body["active_plan"] is None
    assert body["has_any_workout_history"] is True
    assert body["this_week"]["run_count"] == 1


def test_dashboard_plan_and_workouts(client):
    register_and_login(client)
    client.post("/api/plans/generate", json=make_profile_payload())
    _create_workout(client)

    res = client.get("/api/dashboard/summary")
    body = res.json()
    assert body["active_plan"] is not None
    assert body["has_any_workout_history"] is True
    assert len(body["recent_activities"]) == 1


def test_todays_scheduled_workout_present_during_active_plan(client):
    register_and_login(client)
    client.post("/api/plans/generate", json=make_profile_payload())
    res = client.get("/api/dashboard/summary")
    active_plan = res.json()["active_plan"]
    assert active_plan["current_week_detail_available"] is True
    assert active_plan["today_scheduled_workout"] is not None
    assert active_plan["today_scheduled_workout"]["day_of_week"] == date.today().strftime("%A")


def test_dashboard_past_plan_duration_shows_no_detail(client):
    """Beyond total weeks of a plan, the dashboard must not invent a scheduled workout --
    it must explicitly say detail isn't available."""
    register_and_login(client)
    plan_res = client.post("/api/plans/generate", json=make_profile_payload(plan_duration_weeks=8))
    plan_id = plan_res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlan
    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        plan.start_date = date.today() - timedelta(days=65)  # pushes past week 8
        db.commit()
    finally:
        db.close()

    res = client.get("/api/dashboard/summary")
    active_plan = res.json()["active_plan"]
    assert active_plan["current_week"] == 8
    assert active_plan["current_week_detail_available"] is False
    assert active_plan["today_scheduled_workout"] is None


def test_weekly_totals_respect_monday_to_sunday_boundary(client):
    register_and_login(client)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    day_before_week = week_start - timedelta(days=1)  # last Sunday -- must be EXCLUDED

    _create_workout(client, workout_date=week_start.isoformat(), distance_meters=5000, duration_seconds=1500)
    _create_workout(client, workout_date=day_before_week.isoformat(), distance_meters=5000, duration_seconds=1500)

    res = client.get("/api/dashboard/summary")
    this_week = res.json()["this_week"]
    assert this_week["run_count"] == 1  # only the Monday one
    assert this_week["total_distance_km"] == 5.0


def test_monthly_totals_respect_calendar_month_boundary(client):
    register_and_login(client)
    today = date.today()
    month_start = today.replace(day=1)
    day_before_month = month_start - timedelta(days=1)  # last day of previous month -- must be EXCLUDED

    _create_workout(client, workout_date=month_start.isoformat(), distance_meters=10000, duration_seconds=3600)
    _create_workout(client, workout_date=day_before_month.isoformat(), distance_meters=10000, duration_seconds=3600)

    res = client.get("/api/dashboard/summary")
    this_month = res.json()["this_month"]
    assert this_month["run_count"] == 1
    assert this_month["total_distance_km"] == 10.0


def test_deleted_workout_excluded_from_dashboard_totals(client):
    register_and_login(client)
    workout_id = _create_workout(client, distance_meters=5000, duration_seconds=1500).json()["id"]
    client.delete(f"/api/workouts/{workout_id}")

    res = client.get("/api/dashboard/summary")
    body = res.json()
    assert body["this_week"]["run_count"] == 0
    assert body["has_any_workout_history"] is False
    assert body["recent_activities"] == []


def test_average_pace_is_volume_weighted_not_averaged_per_workout(client):
    """Two workouts at very different paces: the correct average is
    total_duration / total_distance, not the mean of the two paces."""
    register_and_login(client)
    # 5km in 20:00 (4:00/km) and 5km in 30:00 (6:00/km).
    # Naive average of paces = 5:00/km. Volume-weighted = 50:00 / 10km = 5:00/km too by
    # coincidence at equal distances -- use unequal distances to differentiate.
    _create_workout(client, distance_meters=5000, duration_seconds=1200)   # 4:00/km
    _create_workout(client, distance_meters=15000, duration_seconds=5400)  # 6:00/km, 3x the volume

    res = client.get("/api/dashboard/summary")
    this_week = res.json()["this_week"]
    # Volume-weighted: (1200+5400) / (20000/1000) = 6600/20 = 330 sec/km = 05:30/km
    # Naive per-workout average would incorrectly give (240+360)/2 = 300 sec/km = 05:00/km
    assert this_week["average_pace_display"] == "05:30 /km"
