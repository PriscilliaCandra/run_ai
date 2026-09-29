"""
Evaluation submission and statistics coverage: rule_based vs ai_personalized
disaggregation, N=0/1/2+ statistics handling, and a direct proof that the
per-test database reset (tests/conftest.py) actually isolates tests from
each other.
"""
from tests.factories import make_profile_payload


def _submit_evaluation(client, plan_id, plan_type, personalization=4, usefulness=4, clarity=4, confidence=4, comments=None):
    return client.post("/api/evaluations", json={
        "training_plan_id": plan_id,
        "evaluated_plan_type": plan_type,
        "personalization_score": personalization,
        "usefulness_score": usefulness,
        "clarity_score": clarity,
        "confidence_score": confidence,
        "comments": comments,
    })


def _generate_plan(client):
    res = client.post("/api/plans/generate", json=make_profile_payload())
    assert res.status_code == 201
    return res.json()["plan_id"]


def test_empty_statistics_are_well_formed_not_null(client):
    stats = client.get("/api/evaluations/stats").json()

    assert stats["total_evaluations"] == 0
    for group in ("rule_based_stats", "ai_personalized_stats"):
        g = stats[group]
        assert g["count"] == 0
        for dim in ("personalization", "usefulness", "clarity", "confidence"):
            assert g[dim]["mean"] is None
            assert g[dim]["median"] is None
            assert g[dim]["std_dev"] is None
        assert g["overall_mean"] is None


def test_rule_based_evaluation_is_recorded_under_its_own_type(client):
    plan_id = _generate_plan(client)
    res = _submit_evaluation(client, plan_id, "rule_based", personalization=3, usefulness=4, clarity=5, confidence=4)
    assert res.status_code == 201
    assert res.json()["evaluated_plan_type"] == "rule_based"

    stats = client.get("/api/evaluations/stats").json()
    assert stats["rule_based_stats"]["count"] == 1
    assert stats["ai_personalized_stats"]["count"] == 0


def test_ai_personalized_evaluation_is_recorded_under_its_own_type(client):
    plan_id = _generate_plan(client)
    res = _submit_evaluation(client, plan_id, "ai_personalized", personalization=5, usefulness=5, clarity=5, confidence=5)
    assert res.status_code == 201
    assert res.json()["evaluated_plan_type"] == "ai_personalized"

    stats = client.get("/api/evaluations/stats").json()
    assert stats["ai_personalized_stats"]["count"] == 1
    assert stats["rule_based_stats"]["count"] == 0


def test_n_equals_one_statistics_have_no_standard_deviation(client):
    plan_id = _generate_plan(client)
    _submit_evaluation(client, plan_id, "rule_based", personalization=4, usefulness=4, clarity=4, confidence=4)

    stats = client.get("/api/evaluations/stats").json()
    rb = stats["rule_based_stats"]
    assert rb["count"] == 1
    assert rb["personalization"]["mean"] == 4.0
    assert rb["personalization"]["median"] == 4.0
    assert rb["personalization"]["std_dev"] is None, "SD for a single observation must be null, not 0.0"


def test_n_greater_or_equal_two_statistics_compute_mean_median_sd(client):
    plan_id = _generate_plan(client)
    _submit_evaluation(client, plan_id, "ai_personalized", personalization=3, usefulness=4, clarity=5, confidence=4)
    _submit_evaluation(client, plan_id, "ai_personalized", personalization=5, usefulness=4, clarity=5, confidence=4)

    stats = client.get("/api/evaluations/stats").json()
    ai = stats["ai_personalized_stats"]
    assert ai["count"] == 2
    assert ai["personalization"]["mean"] == 4.0
    assert ai["personalization"]["median"] == 4.0
    assert ai["personalization"]["std_dev"] is not None
    assert ai["personalization"]["std_dev"] > 0


def test_groups_are_never_combined_into_a_single_score(client):
    """The stats response must keep the two plan types fully separate: no
    top-level blended/combined score should exist anywhere in the payload."""
    plan_id = _generate_plan(client)
    _submit_evaluation(client, plan_id, "rule_based", personalization=1, usefulness=1, clarity=1, confidence=1)
    _submit_evaluation(client, plan_id, "ai_personalized", personalization=5, usefulness=5, clarity=5, confidence=5)

    stats = client.get("/api/evaluations/stats").json()
    assert "overall_mean" not in stats, "no combined score should exist at the top level of the stats response"
    assert stats["rule_based_stats"]["overall_mean"] == 1.0
    assert stats["ai_personalized_stats"]["overall_mean"] == 5.0


def test_submitting_for_a_nonexistent_plan_is_rejected(client):
    res = _submit_evaluation(client, "not-a-real-plan-id", "rule_based")
    assert res.status_code == 404


def test_database_is_isolated_between_tests_part_a(client):
    """Leaves one evaluation behind; part_b (regardless of run order) must not see it."""
    plan_id = _generate_plan(client)
    _submit_evaluation(client, plan_id, "rule_based")
    stats = client.get("/api/evaluations/stats").json()
    assert stats["total_evaluations"] == 1


def test_database_is_isolated_between_tests_part_b(client):
    """If the per-test schema reset in conftest.py were broken, this would see
    leftover data from test_database_is_isolated_between_tests_part_a."""
    stats = client.get("/api/evaluations/stats").json()
    assert stats["total_evaluations"] == 0
