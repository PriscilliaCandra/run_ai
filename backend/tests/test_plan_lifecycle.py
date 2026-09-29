"""
Consumer plan lifecycle coverage: start_date/status assignment, single
active plan per user (previous plan archived), week-1
training_plan_workouts materialization, and the anonymous-research-plan
regression proving zero rows/fields are added for the unauthenticated flow.
"""
from datetime import date

from tests.factories import make_profile_payload, register_and_login


def test_anonymous_plan_generation_creates_zero_training_plan_workouts(client):
    res = client.post("/api/plans/generate", json=make_profile_payload())
    plan_id = res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlanWorkout, TrainingPlan

    db = SessionLocal()
    try:
        count = db.query(TrainingPlanWorkout).filter(TrainingPlanWorkout.training_plan_id == plan_id).count()
        assert count == 0
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert plan.start_date is None
        assert plan.status is None
    finally:
        db.close()


def test_consumer_plan_generation_creates_exactly_seven_week_one_workouts(client):
    register_and_login(client)
    res = client.post("/api/plans/generate", json=make_profile_payload())
    plan_id = res.json()["plan_id"]

    workouts_res = client.get(f"/api/plans/{plan_id}/workouts")
    assert workouts_res.status_code == 200
    workouts = workouts_res.json()
    assert len(workouts) == 7
    assert all(w["week_number"] == 1 for w in workouts)
    days = {w["day_of_week"] for w in workouts}
    assert days == {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}


def test_consumer_plan_gets_start_date_and_active_status(client):
    register_and_login(client)
    res = client.post("/api/plans/generate", json=make_profile_payload())
    plan_id = res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert plan.status == "active"
        assert plan.start_date == date.today()
    finally:
        db.close()


def test_only_one_active_consumer_plan_previous_becomes_archived(client):
    register_and_login(client)
    first_res = client.post("/api/plans/generate", json=make_profile_payload())
    first_plan_id = first_res.json()["plan_id"]

    second_res = client.post("/api/plans/generate", json=make_profile_payload())
    second_plan_id = second_res.json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        first_plan = db.query(TrainingPlan).filter(TrainingPlan.id == first_plan_id).first()
        second_plan = db.query(TrainingPlan).filter(TrainingPlan.id == second_plan_id).first()
        assert first_plan.status == "archived"
        assert second_plan.status == "active"

        active_count = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.user_id == first_plan.user_id, TrainingPlan.status == "active")
            .count()
        )
        assert active_count == 1
    finally:
        db.close()


def test_archiving_one_users_plan_never_affects_another_users_plan(client):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    register_and_login(client, email="lifecycle-user-a@example.com")
    plan_a = client.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]

    client_b = TestClient(fastapi_app)
    client_b.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(client_b, email="lifecycle-user-b@example.com")
    plan_b1 = client_b.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]
    plan_b2 = client_b.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]

    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        assert db.query(TrainingPlan).filter(TrainingPlan.id == plan_a).first().status == "active"
        assert db.query(TrainingPlan).filter(TrainingPlan.id == plan_b1).first().status == "archived"
        assert db.query(TrainingPlan).filter(TrainingPlan.id == plan_b2).first().status == "active"
    finally:
        db.close()


def test_plan_workouts_endpoint_ownership_matches_plan_endpoint(client):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    register_and_login(client, email="plan-workouts-owner@example.com")
    plan_id = client.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]

    client_b = TestClient(fastapi_app)
    client_b.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(client_b, email="plan-workouts-other@example.com")

    assert client_b.get(f"/api/plans/{plan_id}/workouts").status_code == 404
    assert client.get(f"/api/plans/{plan_id}/workouts").status_code == 200


def test_anonymous_plan_workouts_endpoint_stays_open_and_returns_empty_list(client):
    plan_id = client.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]
    res = client.get(f"/api/plans/{plan_id}/workouts")
    assert res.status_code == 200
    assert res.json() == []


def test_list_my_plans_only_shows_own_plans(client):
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    register_and_login(client, email="mine-user-a@example.com")
    plan_a = client.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]

    client_b = TestClient(fastapi_app)
    client_b.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(client_b, email="mine-user-b@example.com")
    plan_b = client_b.post("/api/plans/generate", json=make_profile_payload()).json()["plan_id"]

    mine_a = client.get("/api/plans/mine").json()
    assert [p["plan_id"] for p in mine_a] == [plan_a]

    mine_b = client_b.get("/api/plans/mine").json()
    assert [p["plan_id"] for p in mine_b] == [plan_b]


def test_list_my_plans_requires_authentication(client):
    res = client.get("/api/plans/mine")
    assert res.status_code == 401
