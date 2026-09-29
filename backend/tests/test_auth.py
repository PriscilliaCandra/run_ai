"""
Registration, login, logout, and session-lifecycle coverage.
"""
from datetime import datetime, timedelta

from app.auth.security import hash_token
from app.database import SessionLocal
from app.models import Session as SessionModel, User
from tests.factories import make_register_payload, register_and_login, unique_email


def test_valid_registration_creates_account_and_session_cookie(client):
    payload = make_register_payload()
    res = client.post("/api/auth/register", json=payload)

    assert res.status_code == 201
    body = res.json()
    assert body["email"] == payload["email"]
    assert body["display_name"] == payload["display_name"]
    assert "password" not in body and "password_hash" not in body

    # A session cookie was set (client persists it for subsequent requests).
    assert client.cookies.get("session_token") is not None

    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == payload["email"]


def test_registration_normalizes_and_enforces_unique_email(client):
    email = unique_email()
    first = client.post("/api/auth/register", json=make_register_payload(email=email.upper()))
    assert first.status_code == 201
    assert first.json()["email"] == email  # normalized to lowercase

    second = client.post("/api/auth/register", json=make_register_payload(email=email))
    assert second.status_code == 409


def test_registration_rejects_invalid_email(client):
    res = client.post("/api/auth/register", json=make_register_payload(email="not-an-email"))
    assert res.status_code == 422


def test_registration_rejects_weak_password(client):
    res = client.post("/api/auth/register", json=make_register_payload(password="short"))
    assert res.status_code == 422

    res2 = client.post("/api/auth/register", json=make_register_payload(password="alllettersnodigits"))
    assert res2.status_code == 422


def test_registration_rejects_missing_fields(client):
    res = client.post("/api/auth/register", json={"email": unique_email()})
    assert res.status_code == 422


def test_valid_login_creates_session(client):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)
    client.post("/api/auth/logout")  # clear the auto-login session first

    res = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert res.status_code == 200
    assert client.cookies.get("session_token") is not None


def test_login_with_wrong_password_is_rejected_generically(client):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)
    client.post("/api/auth/logout")

    res = client.post("/api/auth/login", json={"email": payload["email"], "password": "WrongPassword123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


def test_login_with_unknown_email_is_rejected_with_same_generic_message(client):
    res = client.post("/api/auth/login", json={"email": unique_email(), "password": "WhateverPassword123"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password."


def test_logout_revokes_session_and_blocks_further_protected_requests(client):
    register_and_login(client)
    raw_token = client.cookies.get("session_token")
    assert raw_token is not None

    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 204

    # The session must be revoked server-side, not just cleared client-side.
    db = SessionLocal()
    try:
        session_row = db.query(SessionModel).filter(SessionModel.token_hash == hash_token(raw_token)).first()
        assert session_row is not None
        assert session_row.revoked_at is not None
    finally:
        db.close()

    # Re-attach the now-revoked cookie manually and confirm it's rejected.
    client.cookies.set("session_token", raw_token)
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401


def test_expired_session_is_rejected(client):
    register_and_login(client)
    raw_token = client.cookies.get("session_token")

    db = SessionLocal()
    try:
        session_row = db.query(SessionModel).filter(SessionModel.token_hash == hash_token(raw_token)).first()
        session_row.expires_at = datetime.utcnow() - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_revoked_session_is_rejected(client):
    register_and_login(client)
    raw_token = client.cookies.get("session_token")

    db = SessionLocal()
    try:
        session_row = db.query(SessionModel).filter(SessionModel.token_hash == hash_token(raw_token)).first()
        session_row.revoked_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_unauthenticated_request_to_protected_endpoint_is_rejected(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_password_is_never_stored_in_plaintext(client):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).first()
        assert user is not None
        assert user.password_hash != payload["password"]
        assert payload["password"] not in user.password_hash
        # Argon2 hashes are self-identifying.
        assert user.password_hash.startswith("$argon2")
    finally:
        db.close()
