"""User profile (consumer runner profile, separate from the anonymous
research RunnerProfile) coverage."""
from tests.factories import register_and_login


def test_profile_requires_authentication(client):
    res = client.get("/api/users/me/profile")
    assert res.status_code == 401


def test_new_user_has_an_empty_profile_by_default(client):
    register_and_login(client)
    res = client.get("/api/users/me/profile")
    assert res.status_code == 200
    body = res.json()
    assert body["age"] is None
    assert body["pb_5k"] is None


def test_partial_patch_only_updates_sent_fields(client):
    register_and_login(client)

    client.patch("/api/users/me/profile", json={"age": 28, "experience_level": "Intermediate"})
    res = client.patch("/api/users/me/profile", json={"pb_5k": "22:30"})

    assert res.status_code == 200
    body = res.json()
    assert body["pb_5k"] == "22:30"
    assert body["age"] == 28  # untouched by the second, partial PATCH
    assert body["experience_level"] == "Intermediate"


def test_profile_rejects_invalid_pace_format(client):
    register_and_login(client)
    res = client.patch("/api/users/me/profile", json={"pb_5k": "not-a-time"})
    assert res.status_code == 422


def test_profile_does_not_require_legal_name_or_unnecessary_fields():
    """The registration schema only requires email/password/display_name --
    no legal name, address, or other unnecessary PII."""
    from app.auth.schemas import RegisterRequest
    fields = set(RegisterRequest.model_fields.keys())
    assert fields == {"email", "password", "display_name"}
