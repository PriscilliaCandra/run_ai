"""
End-to-end API coverage: health, plan generation, plan retrieval, and basic
input validation. Evaluation-submission/statistics endpoints are covered in
tests/test_evaluation.py. Every test here runs against the isolated temp
database from tests/conftest.py, never the real running_research.db.
"""
from tests.factories import make_profile_payload


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert "safety_disclaimer" in body


def test_plan_generation_returns_baseline_and_ai_plan(client):
    res = client.post("/api/plans/generate", json=make_profile_payload())
    assert res.status_code == 201
    body = res.json()

    assert body["calculated_vdot"] > 0
    assert len(body["rule_based_plan"]["week_1_plan"]["workouts"]) == 7
    assert len(body["ai_personalized_plan"]["workouts"]) == 7
    # Offline fallback is used in tests (no API keys configured) and must
    # never diverge from the rule-based baseline's numeric constraints.
    assert body["ai_personalized_plan"]["weekly_mileage_km"] == body["rule_based_plan"]["week_1_plan"]["weekly_mileage_km"]


def test_plan_generation_handles_single_training_day(client):
    payload = make_profile_payload(training_days_per_week=1, preferred_training_days=["Sunday"])
    res = client.post("/api/plans/generate", json=payload)
    assert res.status_code == 201
    workouts = res.json()["rule_based_plan"]["week_1_plan"]["workouts"]
    active = [w for w in workouts if w["workout_type"] != "Rest & Recovery"]
    assert len(active) == 1
    assert active[0]["workout_type"] == "Long Run"


def test_plan_retrieval_by_id(client):
    gen_res = client.post("/api/plans/generate", json=make_profile_payload())
    plan_id = gen_res.json()["plan_id"]

    get_res = client.get(f"/api/plans/{plan_id}")
    assert get_res.status_code == 200
    assert get_res.json()["plan_id"] == plan_id


def test_plan_retrieval_for_unknown_id_returns_404(client):
    res = client.get("/api/plans/does-not-exist")
    assert res.status_code == 404


def test_invalid_pb_5k_format_is_rejected(client):
    payload = make_profile_payload(pb_5k="not-a-time")
    res = client.post("/api/plans/generate", json=payload)
    assert res.status_code == 422


def test_invalid_pb_10k_format_is_rejected(client):
    payload = make_profile_payload(pb_10k="way too slow")
    res = client.post("/api/plans/generate", json=payload)
    assert res.status_code == 422


def test_valid_pb_10k_format_is_accepted(client):
    payload = make_profile_payload(pb_10k="52:10")
    res = client.post("/api/plans/generate", json=payload)
    assert res.status_code == 201


def test_missing_pb_10k_is_accepted_since_it_is_optional(client):
    payload = make_profile_payload(pb_10k=None)
    res = client.post("/api/plans/generate", json=payload)
    assert res.status_code == 201


def test_invalid_training_days_per_week_is_rejected(client):
    payload = make_profile_payload(training_days_per_week=8)  # schema max is 7
    res = client.post("/api/plans/generate", json=payload)
    assert res.status_code == 422
