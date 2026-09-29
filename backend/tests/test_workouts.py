"""
Workout CRUD, validation, pace calculation, ownership/IDOR, soft delete,
and cross-user training_plan_workout linking coverage.
"""
from datetime import date, timedelta

from tests.factories import make_workout_payload, make_profile_payload, register_and_login


def _create_workout(client, **overrides):
    return client.post("/api/workouts", json=make_workout_payload(**overrides))


def test_create_workout_requires_authentication(client):
    res = _create_workout(client)
    assert res.status_code == 401


def test_create_workout_succeeds_and_computes_pace(client):
    register_and_login(client)
    res = _create_workout(client, distance_meters=5000, duration_seconds=1500)  # 25:00 for 5km -> 5:00/km
    assert res.status_code == 201
    body = res.json()
    assert body["distance_km"] == 5.0
    assert body["pace_sec_per_km"] == 300
    assert body["pace_display"] == "05:00 /km"
    # Pace was never sent by the client and is not an accepted input field.
    assert "pace_sec_per_km" not in make_workout_payload()


def test_pace_calculation_across_various_distance_duration_combinations(client):
    register_and_login(client)
    cases = [
        (10000, 3600, 360, "06:00 /km"),   # 10km in 1h -> 6:00/km
        (21097, 6300, 299, "04:59 /km"),   # half marathon-ish
        (1000, 300, 300, "05:00 /km"),
    ]
    for distance_m, duration_s, expected_pace_sec, expected_display in cases:
        res = _create_workout(client, distance_meters=distance_m, duration_seconds=duration_s)
        assert res.status_code == 201
        body = res.json()
        assert body["pace_sec_per_km"] == expected_pace_sec
        assert body["pace_display"] == expected_display


def test_validation_rejects_invalid_distance(client):
    register_and_login(client)
    assert _create_workout(client, distance_meters=0).status_code == 422
    assert _create_workout(client, distance_meters=-100).status_code == 422
    assert _create_workout(client, distance_meters=300_001).status_code == 422


def test_validation_rejects_invalid_duration(client):
    register_and_login(client)
    assert _create_workout(client, duration_seconds=59).status_code == 422
    assert _create_workout(client, duration_seconds=172_801).status_code == 422


def test_validation_rejects_impossible_heart_rate(client):
    register_and_login(client)
    assert _create_workout(client, avg_heart_rate=29).status_code == 422
    assert _create_workout(client, avg_heart_rate=251).status_code == 422
    assert _create_workout(client, avg_heart_rate=170, max_heart_rate=150).status_code == 422  # avg > max


def test_validation_rejects_impossible_cadence(client):
    register_and_login(client)
    assert _create_workout(client, cadence_spm=99).status_code == 422
    assert _create_workout(client, cadence_spm=251).status_code == 422


def test_validation_rejects_invalid_elevation(client):
    register_and_login(client)
    assert _create_workout(client, elevation_gain_m=-1).status_code == 422
    assert _create_workout(client, elevation_gain_m=10_001).status_code == 422


def test_validation_rejects_rpe_outside_scale(client):
    register_and_login(client)
    assert _create_workout(client, rpe=0).status_code == 422
    assert _create_workout(client, rpe=11).status_code == 422


def test_validation_rejects_invalid_workout_type(client):
    register_and_login(client)
    assert _create_workout(client, workout_type="MARATHON_SPRINT").status_code == 422


def test_validation_rejects_future_date(client):
    register_and_login(client)
    future = (date.today() + timedelta(days=1)).isoformat()
    assert _create_workout(client, workout_date=future).status_code == 422


def test_backdated_workout_is_allowed(client):
    register_and_login(client)
    past = (date.today() - timedelta(days=30)).isoformat()
    res = _create_workout(client, workout_date=past)
    assert res.status_code == 201


def test_read_own_workout(client):
    register_and_login(client)
    workout_id = _create_workout(client).json()["id"]
    res = client.get(f"/api/workouts/{workout_id}")
    assert res.status_code == 200
    assert res.json()["id"] == workout_id


def test_update_own_workout_partial_patch(client):
    register_and_login(client)
    workout_id = _create_workout(client, notes="original").json()["id"]

    res = client.patch(f"/api/workouts/{workout_id}", json={"rpe": 7})
    assert res.status_code == 200
    body = res.json()
    assert body["rpe"] == 7
    assert body["notes"] == "original"  # untouched by the partial PATCH


def test_update_rejects_invalid_merged_heart_rate(client):
    register_and_login(client)
    workout_id = _create_workout(client, avg_heart_rate=140, max_heart_rate=170).json()["id"]
    # Only sending a new avg that would exceed the EXISTING max.
    res = client.patch(f"/api/workouts/{workout_id}", json={"avg_heart_rate": 180})
    assert res.status_code == 422


def test_delete_is_soft_and_excluded_from_get(client):
    register_and_login(client)
    workout_id = _create_workout(client).json()["id"]

    del_res = client.delete(f"/api/workouts/{workout_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/workouts/{workout_id}")
    assert get_res.status_code == 404

    from app.database import SessionLocal
    from app.models import WorkoutLog
    db = SessionLocal()
    try:
        row = db.query(WorkoutLog).filter(WorkoutLog.id == workout_id).first()
        assert row is not None  # row still physically exists
        assert row.deleted_at is not None
    finally:
        db.close()


def test_deleted_workout_excluded_from_history_list(client):
    register_and_login(client)
    keep_id = _create_workout(client).json()["id"]
    delete_id = _create_workout(client).json()["id"]
    client.delete(f"/api/workouts/{delete_id}")

    res = client.get("/api/workouts")
    ids = [w["id"] for w in res.json()["items"]]
    assert keep_id in ids
    assert delete_id not in ids


def test_list_workouts_pagination_and_filters(client):
    register_and_login(client)
    for wtype in ["EASY", "EASY", "TEMPO", "LONG_RUN"]:
        _create_workout(client, workout_type=wtype)

    res = client.get("/api/workouts?page=1&page_size=2")
    body = res.json()
    assert body["total"] == 4
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2

    filtered = client.get("/api/workouts?workout_type=TEMPO")
    assert filtered.json()["total"] == 1

    too_big = client.get("/api/workouts?page_size=101")
    assert too_big.status_code == 422


# --- Ownership / IDOR (mandatory) ---

def test_user_a_workout_not_readable_updatable_or_deletable_by_user_b(client):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    register_and_login(client, email="workout-user-a@example.com")
    workout_id = _create_workout(client).json()["id"]

    client_b = TestClient(fastapi_app)
    client_b.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(client_b, email="workout-user-b@example.com")

    assert client_b.get(f"/api/workouts/{workout_id}").status_code == 404
    assert client_b.patch(f"/api/workouts/{workout_id}", json={"rpe": 3}).status_code == 404
    assert client_b.delete(f"/api/workouts/{workout_id}").status_code == 404

    # And it never appears in B's own list.
    assert workout_id not in [w["id"] for w in client_b.get("/api/workouts").json()["items"]]


def test_client_supplied_user_id_is_not_a_field_on_the_create_schema():
    from app.workouts.schemas import WorkoutLogCreate
    assert "user_id" not in WorkoutLogCreate.model_fields
    from app.workouts.schemas import WorkoutLogUpdate
    assert "user_id" not in WorkoutLogUpdate.model_fields


# --- Cross-user training_plan_workout linking (critical security requirement) ---

def test_cannot_link_workout_to_another_users_training_plan_workout(client):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    # User A generates a plan (materializes 7 training_plan_workouts).
    client_a = TestClient(fastapi_app)
    client_a.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(client_a, email="link-user-a@example.com")
    plan_res = client_a.post("/api/plans/generate", json=make_profile_payload())
    plan_id = plan_res.json()["plan_id"]
    tpw_id = client_a.get(f"/api/plans/{plan_id}/workouts").json()[0]["id"]

    # User B tries to log a workout "against" User A's scheduled workout.
    register_and_login(client, email="link-user-b@example.com")
    res = _create_workout(client, training_plan_workout_id=tpw_id)
    assert res.status_code == 400  # rejected, never silently linked

    # Also rejected on update.
    own_workout_id = _create_workout(client).json()["id"]
    update_res = client.patch(f"/api/workouts/{own_workout_id}", json={"training_plan_workout_id": tpw_id})
    assert update_res.status_code == 400


def test_can_link_workout_to_own_training_plan_workout(client):
    plan_res = client.post("/api/plans/generate", json=make_profile_payload())
    assert plan_res.status_code == 201  # anonymous so far -- now attach a user
    # Redo as an authenticated user so the plan is owned and materialized.
    register_and_login(client, email="link-own@example.com")
    plan_res = client.post("/api/plans/generate", json=make_profile_payload())
    plan_id = plan_res.json()["plan_id"]
    tpw_id = client.get(f"/api/plans/{plan_id}/workouts").json()[0]["id"]

    res = _create_workout(client, training_plan_workout_id=tpw_id)
    assert res.status_code == 201
    assert res.json()["training_plan_workout_id"] == tpw_id


def test_nonexistent_training_plan_workout_id_is_rejected(client):
    register_and_login(client)
    res = _create_workout(client, training_plan_workout_id="not-a-real-id")
    assert res.status_code == 400
