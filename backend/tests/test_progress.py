"""
Phase 4: deterministic weekly volume/consistency trend + observation
sentences (GET /api/dashboard/progress). See PHASE_4_DESIGN.md for the full
rationale behind every threshold exercised here.

Covers: weekly bucketing (unit), week/month/year boundaries, the current
partial week, empty weeks, volume-weighted pace, logged-days counting,
standalone/RACE-workout inclusion, deterministic observation eligibility and
thresholds, API-level behavior (auth, bounds, deleted-workout exclusion,
end-to-end fixture), and the mandatory cross-user ownership test.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from app.workouts.service import bucket_weekly_totals, generate_observations
from tests.conftest import VALID_TEST_ORIGIN
from tests.factories import make_workout_payload, register_and_login


def _fake_row(workout_date, distance_meters=5000, duration_seconds=1800):
    """A minimal stand-in for a WorkoutLog row -- bucket_weekly_totals only
    ever reads .workout_date/.distance_meters/.duration_seconds, so a plain
    object is sufficient and keeps these tests free of any database access."""
    return SimpleNamespace(
        workout_date=workout_date,
        distance_meters=distance_meters,
        duration_seconds=duration_seconds,
    )


# --- bucket_weekly_totals: unit tests, no DB ---

def test_bucket_weekly_totals_single_week_sums_correctly():
    monday = date(2026, 9, 21)  # a Monday
    rows = [_fake_row(monday, 5000, 1500), _fake_row(monday + timedelta(days=2), 10000, 3600)]
    buckets = bucket_weekly_totals(rows, monday, num_weeks=1, today=monday)
    assert len(buckets) == 1
    b = buckets[0]
    assert b.week_start == monday
    assert b.week_end == monday + timedelta(days=6)
    assert b.run_count == 2
    assert b.total_distance_km == 15.0
    assert b.total_duration_seconds == 5100
    assert b.logged_days_count == 2


def test_bucket_weekly_totals_sunday_vs_next_monday_land_in_different_buckets():
    sunday = date(2026, 9, 27)
    monday = sunday + timedelta(days=1)
    rows = [_fake_row(sunday), _fake_row(monday)]
    range_start = sunday - timedelta(days=6)  # the Monday that starts sunday's week
    buckets = bucket_weekly_totals(rows, range_start, num_weeks=2, today=monday)
    assert buckets[0].run_count == 1  # week containing the Sunday
    assert buckets[1].run_count == 1  # following week containing the Monday
    assert buckets[0].week_end == sunday
    assert buckets[1].week_start == monday


def test_bucket_weekly_totals_month_boundary():
    monday = date(2026, 1, 26)  # Monday of the week spanning Jan 26 - Feb 1, 2026
    rows = [_fake_row(date(2026, 1, 29)), _fake_row(date(2026, 2, 1))]
    buckets = bucket_weekly_totals(rows, monday, num_weeks=1, today=monday)
    assert buckets[0].run_count == 2


def test_bucket_weekly_totals_year_boundary():
    dec29 = date(2025, 12, 29)  # Monday spanning Dec 29, 2025 - Jan 4, 2026
    rows = [_fake_row(date(2025, 12, 31)), _fake_row(date(2026, 1, 2))]
    buckets = bucket_weekly_totals(rows, dec29, num_weeks=1, today=dec29)
    assert buckets[0].run_count == 2


def test_bucket_weekly_totals_marks_current_week_and_it_is_last():
    monday = date(2026, 9, 21)
    today = monday + timedelta(days=3)  # Thursday of that week
    range_start = monday - timedelta(weeks=2)
    buckets = bucket_weekly_totals([], range_start, num_weeks=3, today=today)
    assert [b.is_current_week for b in buckets] == [False, False, True]
    assert buckets[-1].week_start == monday


def test_bucket_weekly_totals_empty_week_is_zero_valued_not_omitted():
    today = date(2026, 9, 21)
    buckets = bucket_weekly_totals([], today, num_weeks=1, today=today)
    assert len(buckets) == 1
    b = buckets[0]
    assert b.total_distance_km == 0.0
    assert b.total_duration_seconds == 0
    assert b.run_count == 0
    assert b.logged_days_count == 0
    assert b.average_pace_display is None


def test_bucket_weekly_totals_volume_weighted_pace_not_averaged():
    monday = date(2026, 9, 21)
    # 5km @ 4:00/km and 15km @ 6:00/km -> naive avg would be 5:00/km,
    # volume-weighted is 5:30/km (same fixture style as Phase 2's own test).
    rows = [_fake_row(monday, 5000, 1200), _fake_row(monday + timedelta(days=1), 15000, 5400)]
    buckets = bucket_weekly_totals(rows, monday, num_weeks=1, today=monday)
    assert buckets[0].average_pace_display == "05:30 /km"


def test_bucket_weekly_totals_logged_days_counts_distinct_dates():
    monday = date(2026, 9, 21)
    rows = [_fake_row(monday), _fake_row(monday)]  # two runs, same day
    buckets = bucket_weekly_totals(rows, monday, num_weeks=1, today=monday)
    assert buckets[0].run_count == 2
    assert buckets[0].logged_days_count == 1


# --- generate_observations: unit tests, no DB ---

def _buckets_with_distances(distances_km, today=None):
    """Builds 7 fake buckets (SimpleNamespace, duck-typed like
    WeeklyProgressBucket) with the given per-week total_distance_km list
    (oldest first, length 7) and run_count derived as 1 per non-zero week
    unless overridden -- sufficient for exercising generate_observations in
    isolation without going through bucket_weekly_totals."""
    assert len(distances_km) == 7
    return [
        SimpleNamespace(total_distance_km=km, run_count=(3 if km > 0 else 0), logged_days_count=(3 if km > 0 else 0))
        for km in distances_km
    ]


def test_generate_observations_volume_increase():
    # prior 3 weeks: 10km each (30 total); recent 3 weeks: 15km each (45 total) -> +50%
    buckets = _buckets_with_distances([10, 10, 10, 15, 15, 15, 0])
    obs = generate_observations(buckets)
    assert obs == ["Your weekly running distance has increased over the last 3 weeks compared to the 3 weeks before that."]


def test_generate_observations_volume_decrease():
    buckets = _buckets_with_distances([15, 15, 15, 10, 10, 10, 0])
    obs = generate_observations(buckets)
    assert obs == ["Your weekly running distance has decreased over the last 3 weeks compared to the 3 weeks before that."]


def test_generate_observations_volume_within_threshold_no_observation():
    # 30 -> 32 total is a ~6.7% change, below the 10% threshold.
    buckets = _buckets_with_distances([10, 10, 10, 10, 11, 11, 0])
    obs = generate_observations(buckets)
    assert obs == []


def test_generate_observations_prior_below_floor_no_observation():
    # Prior total 3km (< 5.0km floor) even though the percentage would qualify.
    buckets = _buckets_with_distances([1, 1, 1, 10, 10, 10, 0])
    obs = generate_observations(buckets)
    assert obs == []


def test_generate_observations_run_count_gate_blocks_observation():
    buckets = [
        SimpleNamespace(total_distance_km=10, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=10, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=10, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=20, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=20, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=20, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=0, run_count=0, logged_days_count=0),
    ]
    # 30 -> 60 total is +100%, well past threshold, but run_count sums (3 per window) >= 2 so this actually WOULD pass the run-count gate;
    # use run_count=0 per bucket instead to prove the gate blocks it.
    for b in buckets:
        b.run_count = 0
    obs = generate_observations(buckets)
    assert obs == []


def test_generate_observations_consistency_more_often():
    buckets = [
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),  # prior_days_total = 3
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),  # recent_days_total = 6
        SimpleNamespace(total_distance_km=0, run_count=0, logged_days_count=0),
    ]
    obs = generate_observations(buckets)
    assert "You've logged workouts on more days over the last 3 weeks compared to the 3 weeks before that." in obs


def test_generate_observations_consistency_fewer_days():
    buckets = [
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),  # prior_days_total = 6
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),  # recent_days_total = 3
        SimpleNamespace(total_distance_km=0, run_count=0, logged_days_count=0),
    ]
    obs = generate_observations(buckets)
    assert "You've logged workouts on fewer days over the last 3 weeks compared to the 3 weeks before that." in obs


def test_generate_observations_consistency_below_prior_floor_no_observation():
    # prior_days_total = 2 (< 3 floor), even though the difference would otherwise qualify.
    buckets = [
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=5, run_count=1, logged_days_count=1),
        SimpleNamespace(total_distance_km=5, run_count=0, logged_days_count=0),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=5, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=0, run_count=0, logged_days_count=0),
    ]
    obs = generate_observations(buckets)
    assert not any("days" in o for o in obs)


def test_generate_observations_both_eligible_returns_both_in_fixed_order():
    buckets = [
        SimpleNamespace(total_distance_km=10, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=10, run_count=2, logged_days_count=2),
        SimpleNamespace(total_distance_km=10, run_count=2, logged_days_count=2),  # prior: 30km, 6 days
        SimpleNamespace(total_distance_km=15, run_count=4, logged_days_count=4),
        SimpleNamespace(total_distance_km=15, run_count=4, logged_days_count=4),
        SimpleNamespace(total_distance_km=15, run_count=4, logged_days_count=4),  # recent: 45km, 12 days
        SimpleNamespace(total_distance_km=0, run_count=0, logged_days_count=0),
    ]
    obs = generate_observations(buckets)
    assert len(obs) == 2
    assert "distance" in obs[0]
    assert "days" in obs[1]


def test_generate_observations_insufficient_history_returns_empty_list():
    # Fewer than 7 buckets -> structurally insufficient, never an exception.
    assert generate_observations([]) == []
    assert generate_observations(_buckets_with_distances([10, 10, 10, 15, 15, 15, 0])[:6]) == []


def test_generate_observations_never_exceeds_two():
    buckets = [
        SimpleNamespace(total_distance_km=10, run_count=5, logged_days_count=5),
        SimpleNamespace(total_distance_km=10, run_count=5, logged_days_count=5),
        SimpleNamespace(total_distance_km=10, run_count=5, logged_days_count=5),
        SimpleNamespace(total_distance_km=100, run_count=20, logged_days_count=7),
        SimpleNamespace(total_distance_km=100, run_count=20, logged_days_count=7),
        SimpleNamespace(total_distance_km=100, run_count=20, logged_days_count=7),
        SimpleNamespace(total_distance_km=0, run_count=0, logged_days_count=0),
    ]
    obs = generate_observations(buckets)
    assert len(obs) <= 2


# --- API-level tests ---

def _create_workout_on(client, workout_date, **overrides):
    payload = make_workout_payload(workout_date=workout_date.isoformat(), **overrides)
    res = client.post("/api/workouts", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def test_progress_requires_authentication(client):
    res = client.get("/api/dashboard/progress")
    assert res.status_code == 401


def test_progress_default_weeks_returns_eight_buckets(client):
    register_and_login(client)
    res = client.get("/api/dashboard/progress")
    assert res.status_code == 200
    body = res.json()
    assert len(body["weeks"]) == 8
    assert body["weeks"][-1]["is_current_week"] is True
    assert all(not w["is_current_week"] for w in body["weeks"][:-1])


def test_progress_weeks_boundary_values(client):
    register_and_login(client)
    assert client.get("/api/dashboard/progress?weeks=1").status_code == 200
    assert client.get("/api/dashboard/progress?weeks=26").status_code == 200
    assert len(client.get("/api/dashboard/progress?weeks=1").json()["weeks"]) == 1
    assert len(client.get("/api/dashboard/progress?weeks=26").json()["weeks"]) == 26


def test_progress_weeks_out_of_range_rejected(client):
    register_and_login(client)
    assert client.get("/api/dashboard/progress?weeks=0").status_code == 422
    assert client.get("/api/dashboard/progress?weeks=27").status_code == 422


def test_progress_empty_new_user_all_zero_no_observations(client):
    register_and_login(client)
    body = client.get("/api/dashboard/progress").json()
    assert body["observations"] == []
    for w in body["weeks"]:
        assert w["total_distance_km"] == 0.0
        assert w["total_duration_seconds"] == 0
        assert w["run_count"] == 0
        assert w["logged_days_count"] == 0
        assert w["average_pace_display"] is None


def test_progress_excludes_deleted_workouts(client):
    register_and_login(client)
    today = date.today()
    workout = _create_workout_on(client, today, distance_meters=5000, duration_seconds=1500)
    before = client.get("/api/dashboard/progress").json()
    current_before = before["weeks"][-1]
    assert current_before["run_count"] == 1

    del_res = client.delete(f"/api/workouts/{workout['id']}")
    assert del_res.status_code == 204

    after = client.get("/api/dashboard/progress").json()
    current_after = after["weeks"][-1]
    assert current_after["run_count"] == 0
    assert current_after["total_distance_km"] == 0.0


def test_progress_standalone_and_race_workouts_count_fully(client):
    register_and_login(client)
    today = date.today()
    _create_workout_on(client, today, distance_meters=5000, duration_seconds=1500, workout_type="EASY")
    _create_workout_on(client, today, distance_meters=10000, duration_seconds=3000, workout_type="RACE")
    body = client.get("/api/dashboard/progress").json()
    current = body["weeks"][-1]
    assert current["run_count"] == 2
    assert current["total_distance_km"] == 15.0


def test_progress_hand_computed_fixture_end_to_end(client):
    """
    A full fixture spanning 7 weeks with known values, asserting exact
    computed totals AND the resulting observation -- not just isolated unit
    behavior. Uses direct DB writes (via the ORM) to control workout_date
    precisely across past weeks, since the API itself rejects future dates
    and this fixture must place data in specific past weeks relative to
    "today" regardless of when the test suite runs.
    """
    register_and_login(client, email="progress-fixture@example.com")

    from app.database import SessionLocal
    from app.models import User, WorkoutLog
    import uuid

    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "progress-fixture@example.com").first()
        # Prior window (weeks -6,-5,-4): 10km per week, 1 run/week -> prior_total_km=30, prior_run_count=3, prior_days_total=3
        # Recent window (weeks -3,-2,-1): 15km per week, 1 run/week -> recent_total_km=45, recent_run_count=3
        for weeks_back in [6, 5, 4, 3, 2, 1]:
            week_start = current_week_start - timedelta(weeks=weeks_back)
            distance = 10000 if weeks_back >= 4 else 15000
            db.add(WorkoutLog(
                id=str(uuid.uuid4()),
                user_id=user.id,
                workout_date=week_start,
                distance_meters=distance,
                duration_seconds=distance // 1000 * 300,  # 5:00/km flat, simplifies expected pace math
                workout_type="EASY",
            ))
        db.commit()
    finally:
        db.close()

    body = client.get("/api/dashboard/progress?weeks=7").json()
    weeks = body["weeks"]
    assert len(weeks) == 7
    # oldest-first: index 0 = weeks_back=6 ... index 5 = weeks_back=1, index 6 = current (empty)
    for i in range(6):
        assert weeks[i]["run_count"] == 1
    assert weeks[6]["run_count"] == 0
    assert weeks[6]["is_current_week"] is True
    assert weeks[0]["total_distance_km"] == 10.0
    assert weeks[5]["total_distance_km"] == 15.0

    assert body["observations"] == [
        "Your weekly running distance has increased over the last 3 weeks compared to the 3 weeks before that."
    ]


def test_progress_cross_user_isolation(client):
    """Mandatory ownership test: User B's workouts must never appear in
    User A's progress response."""
    client_b = _second_client("progress-user-b@example.com")
    _create_workout_on(client_b, date.today(), distance_meters=20000, duration_seconds=6000)

    register_and_login(client, email="progress-user-a@example.com")
    body = client.get("/api/dashboard/progress").json()
    current = body["weeks"][-1]
    assert current["run_count"] == 0
    assert current["total_distance_km"] == 0.0


def _second_client(email: str):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    c = TestClient(fastapi_app)
    c.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(c, email=email)
    return c
