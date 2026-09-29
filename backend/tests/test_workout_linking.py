"""
Phase 3: plan <-> actual workout integration.

Covers scheduled_date derivation, derived completion state (scheduled /
completed / missed -- never stored), linking/unlinking, the archived-plan
locked decision (new links rejected, historical links preserved), planned-vs-
actual response enrichment, dashboard integration (today / upcoming / week-1
completion count), history integration, and the mandatory two-user /
indirect-IDOR security tests.
"""
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.workouts.service import scheduled_date_for, derive_completion_status, is_rest_day
from tests.conftest import VALID_TEST_ORIGIN
from tests.factories import make_profile_payload, make_workout_payload, register_and_login


def _second_client(email: str) -> TestClient:
    c = TestClient(fastapi_app)
    c.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(c, email=email)
    return c


def _generate_owned_plan(client, **overrides):
    res = client.post("/api/plans/generate", json=make_profile_payload(**overrides))
    assert res.status_code == 201
    return res.json()["plan_id"]


def _plan_workouts(client, plan_id):
    res = client.get(f"/api/plans/{plan_id}/workouts")
    assert res.status_code == 200
    return res.json()


def _set_plan_status(plan_id: str, status: str):
    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        plan.status = status
        db.commit()
    finally:
        db.close()


def _set_plan_start_date(plan_id: str, new_start_date: date):
    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        plan.start_date = new_start_date
        db.commit()
    finally:
        db.close()


# --- scheduled_date_for: pure function, all boundary cases ---

def test_scheduled_date_for_start_on_monday():
    monday = date(2026, 9, 28)
    assert scheduled_date_for(monday, "Monday") == date(2026, 9, 28)
    assert scheduled_date_for(monday, "Tuesday") == date(2026, 9, 29)
    assert scheduled_date_for(monday, "Sunday") == date(2026, 10, 4)


def test_scheduled_date_for_start_mid_week():
    wednesday = date(2026, 9, 30)  # a Wednesday
    # Every weekday name still appears exactly once in [wed .. next_tue].
    assert scheduled_date_for(wednesday, "Wednesday") == date(2026, 9, 30)
    assert scheduled_date_for(wednesday, "Thursday") == date(2026, 10, 1)
    assert scheduled_date_for(wednesday, "Monday") == date(2026, 10, 5)   # wraps to the following Monday
    assert scheduled_date_for(wednesday, "Tuesday") == date(2026, 10, 6)  # the last day of the 7-day window


def test_scheduled_date_for_start_on_sunday():
    sunday = date(2026, 10, 4)
    assert scheduled_date_for(sunday, "Sunday") == date(2026, 10, 4)
    assert scheduled_date_for(sunday, "Monday") == date(2026, 10, 5)
    assert scheduled_date_for(sunday, "Saturday") == date(2026, 10, 10)


def test_scheduled_date_for_covers_all_seven_days_exactly_once():
    for start in [date(2026, 9, 28), date(2026, 9, 30), date(2026, 10, 4)]:
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        mapped = {scheduled_date_for(start, d) for d in days}
        assert mapped == {start + timedelta(days=i) for i in range(7)}


def test_derive_completion_status_pure_function():
    today = date(2026, 9, 29)
    assert derive_completion_status(today, today, has_active_log=True) == "completed"
    assert derive_completion_status(today - timedelta(days=1), today, has_active_log=True) == "completed"
    assert derive_completion_status(today - timedelta(days=1), today, has_active_log=False) == "missed"
    assert derive_completion_status(today, today, has_active_log=False) == "scheduled"
    assert derive_completion_status(today + timedelta(days=1), today, has_active_log=False) == "scheduled"


def test_is_rest_day():
    assert is_rest_day("Rest & Recovery") is True
    assert is_rest_day("rest day") is True
    assert is_rest_day("Interval Training") is False
    assert is_rest_day("Long Run") is False


# --- Planned workout reading (no fabrication) ---

def test_own_plan_schedule_is_readable_and_carries_scheduled_dates(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    workouts = _plan_workouts(client, plan_id)
    assert len(workouts) == 56  # 8 weeks * 7 days
    for w in workouts:
        assert w["scheduled_date"] is not None
    # Every calendar date in the 56-day window is represented exactly once.
    dates = {w["scheduled_date"] for w in workouts}
    assert len(dates) == 56


def test_no_fabricated_schedule_past_plan_duration(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    # Push start_date back past the full 8-week duration (60 days)
    _set_plan_start_date(plan_id, date.today() - timedelta(days=60))

    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    active = res.json()["active_plan"]
    assert active["current_week_detail_available"] is False
    assert active["today_scheduled_workout"] is None
    assert active["upcoming_scheduled_workout"] is None
    assert active["current_week_completed_count"] is None
    assert active["current_week_total_loggable_count"] is None


def test_anonymous_plan_workouts_have_no_scheduled_date_or_completion(client):
    plan_id = client.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]
    workouts = _plan_workouts(client, plan_id)
    assert workouts == []  # unchanged Phase 2 regression: anonymous plans get zero rows


# --- Linking ---

def test_own_workout_can_link_to_own_scheduled_workout(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = _plan_workouts(client, plan_id)[0]

    res = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw["id"]))
    assert res.status_code == 201
    body = res.json()
    assert body["training_plan_workout_id"] == tpw["id"]
    assert body["linked_scheduled_workout"]["id"] == tpw["id"]
    assert body["linked_scheduled_workout"]["completion_status"] in ("completed", None)


def test_cross_user_scheduled_workout_link_rejected_on_create_and_update(client):
    owner = _second_client("linking-owner@example.com")
    plan_id = _generate_owned_plan(owner)
    tpw_id = _plan_workouts(owner, plan_id)[0]["id"]

    register_and_login(client, email="linking-attacker@example.com")
    res = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw_id))
    assert res.status_code == 400

    own_workout_id = client.post("/api/workouts", json=make_workout_payload()).json()["id"]
    update_res = client.patch(f"/api/workouts/{own_workout_id}", json={"training_plan_workout_id": tpw_id})
    assert update_res.status_code == 400


def test_new_link_to_archived_plan_is_rejected(client):
    register_and_login(client)
    old_plan_id = _generate_owned_plan(client)
    old_tpw_id = _plan_workouts(client, old_plan_id)[0]["id"]

    # Generating a second plan archives the first (existing Phase 2 lifecycle rule).
    _generate_owned_plan(client)
    from app.database import SessionLocal
    from app.models import TrainingPlan
    db = SessionLocal()
    try:
        assert db.query(TrainingPlan).filter(TrainingPlan.id == old_plan_id).first().status == "archived"
    finally:
        db.close()

    res = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=old_tpw_id))
    assert res.status_code == 400
    assert "archived" in res.json()["detail"].lower()

    # Also rejected as a NEW link via update.
    own_workout_id = client.post("/api/workouts", json=make_workout_payload()).json()["id"]
    update_res = client.patch(f"/api/workouts/{own_workout_id}", json={"training_plan_workout_id": old_tpw_id})
    assert update_res.status_code == 400


def test_existing_historical_link_to_now_archived_plan_remains_readable(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw_id = _plan_workouts(client, plan_id)[0]["id"]

    # Link while the plan is still active.
    workout_id = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw_id)).json()["id"]

    # Now archive it (by generating a new plan -- the normal lifecycle path).
    _generate_owned_plan(client)

    # The historical link must still read back correctly.
    res = client.get(f"/api/workouts/{workout_id}")
    assert res.status_code == 200
    assert res.json()["training_plan_workout_id"] == tpw_id
    assert res.json()["linked_scheduled_workout"]["id"] == tpw_id

    # And the archived plan's own workouts endpoint still shows the link.
    workouts = _plan_workouts(client, plan_id)
    linked_row = next(w for w in workouts if w["id"] == tpw_id)
    assert len(linked_row["linked_workout_logs"]) == 1
    assert linked_row["linked_workout_logs"][0]["id"] == workout_id


def test_resubmitting_the_same_existing_link_on_an_archived_plan_is_not_rejected(client):
    """A PATCH that resends the workout's own already-linked id (e.g. a form
    resubmitting the full object unchanged) must not fail just because the
    plan was archived in the meantime -- only a genuinely NEW link is blocked."""
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw_id = _plan_workouts(client, plan_id)[0]["id"]
    workout_id = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw_id)).json()["id"]

    _generate_owned_plan(client)  # archives plan_id

    res = client.patch(f"/api/workouts/{workout_id}", json={"training_plan_workout_id": tpw_id, "notes": "unchanged link"})
    assert res.status_code == 200
    assert res.json()["training_plan_workout_id"] == tpw_id


# --- Completion derivation, end to end via the API ---

def test_scheduled_workout_with_no_log_is_scheduled_or_missed(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    workouts = _plan_workouts(client, plan_id)
    today = date.today()
    for w in workouts:
        if w["completion_status"] is None:
            continue  # rest day
        sched = date.fromisoformat(w["scheduled_date"])
        expected = "missed" if sched < today else "scheduled"
        assert w["completion_status"] == expected
        assert w["linked_workout_logs"] == []


def test_linked_active_log_makes_scheduled_workout_completed(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = next(w for w in _plan_workouts(client, plan_id) if w["completion_status"] is not None)

    client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw["id"]))

    updated = next(w for w in _plan_workouts(client, plan_id) if w["id"] == tpw["id"])
    assert updated["completion_status"] == "completed"
    assert len(updated["linked_workout_logs"]) == 1


def test_deleted_linked_log_reverts_completion_state_automatically(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = next(w for w in _plan_workouts(client, plan_id) if w["completion_status"] is not None)
    sched = date.fromisoformat(tpw["scheduled_date"])
    today = date.today()
    expected_after_delete = "missed" if sched < today else "scheduled"

    workout_id = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw["id"])).json()["id"]
    assert next(w for w in _plan_workouts(client, plan_id) if w["id"] == tpw["id"])["completion_status"] == "completed"

    del_res = client.delete(f"/api/workouts/{workout_id}")
    assert del_res.status_code == 204

    reverted = next(w for w in _plan_workouts(client, plan_id) if w["id"] == tpw["id"])
    assert reverted["completion_status"] == expected_after_delete
    assert reverted["linked_workout_logs"] == []  # deleted log must not count


def test_rest_day_never_shows_a_completion_status(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    workouts = _plan_workouts(client, plan_id)
    rest_days = [w for w in workouts if "rest" in w["workout_type"].lower()]
    assert len(rest_days) > 0
    for r in rest_days:
        assert r["completion_status"] is None


# --- Unlink ---

def test_unlink_removes_relationship_but_keeps_the_workout(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = next(w for w in _plan_workouts(client, plan_id) if w["completion_status"] is not None)
    workout_id = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw["id"])).json()["id"]

    res = client.patch(f"/api/workouts/{workout_id}", json={"training_plan_workout_id": None})
    assert res.status_code == 200
    assert res.json()["training_plan_workout_id"] is None
    assert res.json()["linked_scheduled_workout"] is None

    # Workout itself still exists.
    assert client.get(f"/api/workouts/{workout_id}").status_code == 200

    # Scheduled workout no longer considers itself completed by this log.
    reverted = next(w for w in _plan_workouts(client, plan_id) if w["id"] == tpw["id"])
    assert reverted["completion_status"] != "completed"


# --- Planned vs actual response shape ---

def test_workout_response_includes_planned_and_actual_fields(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = next(w for w in _plan_workouts(client, plan_id) if w["completion_status"] is not None)

    res = client.post("/api/workouts", json=make_workout_payload(
        training_plan_workout_id=tpw["id"], distance_meters=5200, duration_seconds=1560,  # 5:00/km
    ))
    body = res.json()
    linked = body["linked_scheduled_workout"]
    assert linked["workout_type"] == tpw["workout_type"]
    assert linked["distance_km"] == tpw["distance_km"]
    assert linked["pace_target"] == tpw["pace_target"]
    assert body["distance_km"] == 5.2
    assert body["pace_display"] == "05:00 /km"


def test_get_workouts_list_enriches_linked_scheduled_workout(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = next(w for w in _plan_workouts(client, plan_id) if w["completion_status"] is not None)
    client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw["id"]))
    client.post("/api/workouts", json=make_workout_payload())  # standalone

    items = client.get("/api/workouts").json()["items"]
    linked_item = next(i for i in items if i["training_plan_workout_id"] == tpw["id"])
    standalone_item = next(i for i in items if i["training_plan_workout_id"] is None)
    assert linked_item["linked_scheduled_workout"]["id"] == tpw["id"]
    assert standalone_item["linked_scheduled_workout"] is None


# --- Dashboard integration ---

def test_dashboard_today_scheduled_carries_completion_and_links(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    workouts = _plan_workouts(client, plan_id)
    today_name = date.today().strftime("%A")
    today_row = next(w for w in workouts if w["day_of_week"] == today_name)

    if today_row["completion_status"] is not None:
        client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=today_row["id"]))

    summary = client.get("/api/dashboard/summary").json()
    active = summary["active_plan"]
    if today_row["completion_status"] is not None:
        assert active["today_scheduled_workout"]["completion_status"] == "completed"
        assert len(active["today_scheduled_workout"]["linked_workout_logs"]) == 1
    else:
        assert active["today_scheduled_workout"]["completion_status"] is None


def test_dashboard_current_week_completion_count_reflects_logged_workouts(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    workouts = _plan_workouts(client, plan_id)
    current_week_loggable = [w for w in workouts if w["week_number"] == 1 and w["completion_status"] is not None]

    summary = client.get("/api/dashboard/summary").json()
    active = summary["active_plan"]
    assert active["current_week_total_loggable_count"] == len(current_week_loggable)
    assert active["current_week_completed_count"] == 0

    client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=current_week_loggable[0]["id"]))

    summary_after = client.get("/api/dashboard/summary").json()
    assert summary_after["active_plan"]["current_week_completed_count"] == 1


def test_dashboard_no_plan_has_no_scheduled_or_count_fields(client):
    register_and_login(client)
    summary = client.get("/api/dashboard/summary").json()
    assert summary["active_plan"] is None


# --- History integration (via GET /api/workouts, which HistoryPage consumes) ---

def test_deleted_workout_excluded_from_history_and_does_not_count_as_completed(client):
    register_and_login(client)
    plan_id = _generate_owned_plan(client)
    tpw = next(w for w in _plan_workouts(client, plan_id) if w["completion_status"] is not None)
    workout_id = client.post("/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw["id"])).json()["id"]

    client.delete(f"/api/workouts/{workout_id}")

    items = client.get("/api/workouts").json()["items"]
    assert workout_id not in [i["id"] for i in items]

    reverted = next(w for w in _plan_workouts(client, plan_id) if w["id"] == tpw["id"])
    assert reverted["completion_status"] != "completed"


# --- Security: two-user / indirect IDOR ---

def test_user_a_cannot_read_user_bs_plan_workouts(client):
    user_b = _second_client("security-b@example.com")
    plan_b = _generate_owned_plan(user_b)

    register_and_login(client, email="security-a@example.com")
    res = client.get(f"/api/plans/{plan_b}/workouts")
    assert res.status_code == 404


def test_user_a_cannot_access_user_bs_workout_by_id(client):
    user_b = _second_client("security-workout-b@example.com")
    workout_b = user_b.post("/api/workouts", json=make_workout_payload()).json()["id"]

    register_and_login(client, email="security-workout-a@example.com")
    assert client.get(f"/api/workouts/{workout_b}").status_code == 404
    assert client.patch(f"/api/workouts/{workout_b}", json={"rpe": 5}).status_code == 404
    assert client.delete(f"/api/workouts/{workout_b}").status_code == 404


def test_user_a_never_sees_user_bs_linked_logs_through_own_plan_workouts_endpoint(client):
    """
    The important indirect-IDOR case: even if User A somehow obtained a
    training_plan_workout_id that coincidentally matched something on their
    OWN plan, User B's logs (linked to User B's OWN, different, scheduled
    workout id) must never appear in User A's GET /api/plans/{A's id}/workouts
    response. Since ids are UUIDs, this test proves the stronger property
    directly: User B's linked logs never appear in ANY response A can reach.
    """
    user_a = client
    register_and_login(user_a, email="indirect-a@example.com")
    plan_a = _generate_owned_plan(user_a)
    tpw_a_id = _plan_workouts(user_a, plan_a)[0]["id"]

    user_b = _second_client("indirect-b@example.com")
    plan_b = _generate_owned_plan(user_b)
    tpw_b = next(w for w in _plan_workouts(user_b, plan_b) if w["completion_status"] is not None)
    workout_b_id = user_b.post(
        "/api/workouts", json=make_workout_payload(training_plan_workout_id=tpw_b["id"])
    ).json()["id"]

    # A's own plan-workouts response must contain zero trace of B's data.
    a_workouts = _plan_workouts(user_a, plan_a)
    all_linked_log_ids = [log["id"] for w in a_workouts for log in w["linked_workout_logs"]]
    assert workout_b_id not in all_linked_log_ids

    # And A cannot read B's scheduled workout row at all (already covered
    # above, re-asserted here for completeness of this specific test).
    assert user_a.get(f"/api/plans/{plan_b}/workouts").status_code == 404
