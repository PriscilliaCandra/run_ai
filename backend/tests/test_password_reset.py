"""
Password reset flow coverage: token expiry, single-use enforcement, and
confirmation that the raw token is never persisted (only its hash).
"""
import logging
from datetime import datetime, timedelta

from app.auth.security import hash_token
from app.database import SessionLocal
from app.models import PasswordResetToken, User
from tests.factories import make_register_payload, unique_email


def _request_reset_and_capture_link(client, caplog, email):
    with caplog.at_level(logging.INFO, logger="app.auth.email_service"):
        res = client.post("/api/auth/forgot-password", json={"email": email})
    assert res.status_code == 200
    # Extract the raw token from the dev-mode log line (never from the API response).
    log_text = " ".join(r.getMessage() for r in caplog.records)
    assert "token=" in log_text
    raw_token = log_text.split("token=")[-1].split()[0].strip()
    return raw_token


def test_forgot_password_never_exposes_the_token_in_the_response(client):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)

    res = client.post("/api/auth/forgot-password", json={"email": payload["email"]})
    assert res.status_code == 200
    body_text = res.text
    assert "token" not in body_text.lower()


def test_forgot_password_returns_same_generic_response_for_unknown_email(client):
    known_payload = make_register_payload()
    client.post("/api/auth/register", json=known_payload)

    res_known = client.post("/api/auth/forgot-password", json={"email": known_payload["email"]})
    res_unknown = client.post("/api/auth/forgot-password", json={"email": unique_email()})

    assert res_known.status_code == res_unknown.status_code == 200
    assert res_known.json() == res_unknown.json()


def test_raw_reset_token_is_never_persisted_only_its_hash(client, caplog):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)

    raw_token = _request_reset_and_capture_link(client, caplog, payload["email"])

    db = SessionLocal()
    try:
        rows = db.query(PasswordResetToken).all()
        assert len(rows) == 1
        assert rows[0].token_hash != raw_token
        assert rows[0].token_hash == hash_token(raw_token)
    finally:
        db.close()


def test_reset_password_with_valid_token_changes_password_and_revokes_sessions(client, caplog):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)
    assert client.cookies.get("session_token") is not None  # logged in from registration

    raw_token = _request_reset_and_capture_link(client, caplog, payload["email"])

    res = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "NewPassword456"})
    assert res.status_code == 200

    # The old session must be revoked by the reset.
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401

    # New password logs in; old password no longer works.
    old_login = client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": payload["email"], "password": "NewPassword456"})
    assert new_login.status_code == 200


def test_reset_token_is_single_use(client, caplog):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)
    raw_token = _request_reset_and_capture_link(client, caplog, payload["email"])

    first = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "FirstNewPass1"})
    assert first.status_code == 200

    second = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "SecondNewPass2"})
    assert second.status_code == 400


def test_expired_reset_token_is_rejected(client, caplog):
    payload = make_register_payload()
    client.post("/api/auth/register", json=payload)
    raw_token = _request_reset_and_capture_link(client, caplog, payload["email"])

    db = SessionLocal()
    try:
        token_row = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == hash_token(raw_token)
        ).first()
        token_row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "WontWork123"})
    assert res.status_code == 400


def test_invalid_reset_token_is_rejected(client):
    res = client.post("/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "WontWork123"})
    assert res.status_code == 400
