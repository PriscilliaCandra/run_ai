"""
CSRF (Origin-check) middleware coverage: a state-changing request that
carries the session cookie must present a matching Origin/Referer, or be
rejected -- see app/core/csrf.py for the chosen strategy and rationale.
"""
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from tests.factories import make_register_payload


def test_mutating_request_without_origin_header_is_rejected():
    client = TestClient(fastapi_app)  # no default Origin header set
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)  # register/login has no cookie yet, allowed
    assert client.cookies.get("session_token") is not None

    res = client.patch("/api/users/me/profile", json={"age": 30})
    assert res.status_code == 403


def test_mutating_request_with_wrong_origin_is_rejected():
    client = TestClient(fastapi_app)
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)

    res = client.patch(
        "/api/users/me/profile",
        json={"age": 30},
        headers={"Origin": "https://evil.example.com"},
    )
    assert res.status_code == 403


def test_mutating_request_with_correct_origin_is_allowed(client):
    """The shared `client` fixture already sets a valid Origin (see conftest.py)."""
    from tests.factories import register_and_login
    register_and_login(client)

    res = client.patch("/api/users/me/profile", json={"age": 30})
    assert res.status_code == 200


def test_get_requests_are_never_blocked_by_csrf_check():
    client = TestClient(fastapi_app)  # no Origin header at all
    res = client.get("/api/health")
    assert res.status_code == 200
