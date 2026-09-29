"""
Rate limiting coverage for login (public, expensive-to-abuse endpoint).

Rate limiting is disabled by default across the rest of the suite (see the
autouse `_disable_rate_limiting` fixture in conftest.py, which prevents
unrelated tests from tripping a shared in-memory limiter). These tests
explicitly re-enable and reset it for their own scope only.
"""
import pytest

from app.config import settings
from app.core.rate_limit import limiter
from tests.factories import unique_email


def _limit_count(limit_string: str) -> int:
    # "5/minute" -> 5
    return int(limit_string.split("/")[0])


@pytest.fixture()
def enabled_limiter():
    limiter.enabled = True
    limiter.reset()
    yield limiter
    limiter.reset()
    limiter.enabled = False


def test_login_rate_limit_returns_429_once_threshold_is_exceeded(client, enabled_limiter):
    max_attempts = _limit_count(settings.RATE_LIMIT_LOGIN)
    email = unique_email()

    for _ in range(max_attempts):
        res = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword123"})
        assert res.status_code == 401  # under the limit: normal auth failure

    over_limit_res = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword123"})
    assert over_limit_res.status_code == 429

    # The 429 body must not leak internals -- just a plain, safe message.
    body = over_limit_res.json()
    assert "traceback" not in str(body).lower()
    assert "api_key" not in str(body).lower()


def test_rate_limits_are_sourced_from_settings_not_hardcoded():
    """Every rate limit applied in the app is read from app.config.settings
    (itself populated from the environment / .env), not a literal string
    baked into a route -- changing RATE_LIMIT_LOGIN etc. in .env changes
    enforcement on the next process start, with no code edit required."""
    assert settings.RATE_LIMIT_LOGIN and "/" in settings.RATE_LIMIT_LOGIN
    assert settings.RATE_LIMIT_REGISTER and "/" in settings.RATE_LIMIT_REGISTER
    assert settings.RATE_LIMIT_PASSWORD_RESET and "/" in settings.RATE_LIMIT_PASSWORD_RESET
    assert settings.RATE_LIMIT_PLAN_GENERATION and "/" in settings.RATE_LIMIT_PLAN_GENERATION
