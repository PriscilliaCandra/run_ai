"""
Ownership / IDOR-prevention coverage. The two-user cross-access test is the
mandatory test explicitly required by the Phase 1 brief: User A's resource
must be completely unreachable by User B, on every verb the resource
supports.
"""
from tests.factories import make_profile_payload, register_and_login


def _generate_plan(client):
    res = client.post("/api/plans/generate", json=make_profile_payload())
    assert res.status_code == 201
    return res.json()["plan_id"]


def test_user_a_plan_is_not_readable_by_user_b(client):
    """The mandatory cross-user ownership test."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    # User A registers, logs in (client already holds A's session), and generates a plan.
    register_and_login(client, email="user-a@example.com")
    plan_id = _generate_plan(client)

    # Confirm A can read their own plan.
    own_res = client.get(f"/api/plans/{plan_id}")
    assert own_res.status_code == 200

    # A separate client/session for User B.
    client_b = TestClient(fastapi_app)
    client_b.headers.update({"Origin": VALID_TEST_ORIGIN})
    register_and_login(client_b, email="user-b@example.com")

    # User B must NOT be able to GET User A's plan -- generic 404, not 403,
    # so the endpoint doesn't even confirm the ID belongs to someone else.
    get_res = client_b.get(f"/api/plans/{plan_id}")
    assert get_res.status_code == 404

    # An anonymous (logged-out) caller must not be able to read it either.
    anon_client = TestClient(fastapi_app)
    anon_client.headers.update({"Origin": VALID_TEST_ORIGIN})
    anon_res = anon_client.get(f"/api/plans/{plan_id}")
    assert anon_res.status_code == 404

    # It must not leak into User B's or anonymous's "recent plans" listing.
    list_res = client_b.get("/api/plans")
    assert plan_id not in [p["plan_id"] for p in list_res.json()]


def test_anonymous_research_plan_remains_readable_without_login(client):
    """Preserving the existing, unauthenticated research flow: an anonymous
    plan (no session at generation time) must stay reachable by anyone,
    exactly as before Phase 1."""
    res = client.post("/api/plans/generate", json=make_profile_payload())
    assert res.status_code == 201
    plan_id = res.json()["plan_id"]

    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    from tests.conftest import VALID_TEST_ORIGIN

    fresh_anonymous_client = TestClient(fastapi_app)
    fresh_anonymous_client.headers.update({"Origin": VALID_TEST_ORIGIN})
    res2 = fresh_anonymous_client.get(f"/api/plans/{plan_id}")
    assert res2.status_code == 200


def test_authenticated_plan_generation_attaches_owning_user(client):
    register_and_login(client)
    plan_id = _generate_plan(client)

    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert plan.user_id is not None
    finally:
        db.close()


def test_anonymous_plan_generation_leaves_user_id_null(client):
    plan_id = _generate_plan(client)  # no login on this client

    from app.database import SessionLocal
    from app.models import TrainingPlan

    db = SessionLocal()
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()
        assert plan.user_id is None
    finally:
        db.close()


def test_client_supplied_user_id_is_ignored_on_profile_update(client):
    """The server must derive ownership only from the session -- a client
    can never set/override user_id via a request body."""
    register_and_login(client, email="ignore-userid@example.com")

    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        other_user = User(email="someone-else@example.com", password_hash="x", display_name="Other")
        db.add(other_user)
        db.commit()
        other_id = other_user.id
    finally:
        db.close()

    res = client.patch("/api/users/me/profile", json={"user_id": other_id, "age": 30})
    assert res.status_code == 200
    assert res.json()["age"] == 30

    me = client.get("/api/auth/me").json()
    from app.database import SessionLocal as SL
    from app.models import UserProfile
    db2 = SL()
    try:
        profile = db2.query(UserProfile).filter(UserProfile.user_id == me["id"]).first()
        assert profile.user_id == me["id"]
        assert profile.user_id != other_id
    finally:
        db2.close()
