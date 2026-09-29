"""
CSRF strategy for the cookie-based session architecture.

Chosen approach (documented here and in README.md -- not claimed to be a
complete/"fully secure" solution on its own, but a deliberate, appropriate
combination for this same-site SPA + API architecture):

1. The session cookie is set with SameSite=Lax (see app/auth/routes.py),
   which already stops the cookie from being attached to most cross-site
   POST/PUT/PATCH/DELETE requests initiated by another site.
2. As defense-in-depth, this middleware additionally requires that any
   state-changing request (POST/PUT/PATCH/DELETE) that carries our session
   cookie present an Origin (or, if absent, Referer) header matching one of
   the configured ALLOWED_ORIGINS. A cross-site page cannot set this header
   to our own origin, so a forged request from another site is rejected
   even in browsers/configurations where SameSite alone isn't sufficient.

Requests with no session cookie (anonymous research usage, and the
login/register calls that create the very first cookie) are not subject to
this check -- there is no authenticated session yet for a forged request to
act on.
"""
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _allowed_origins() -> set:
    return {o.strip().rstrip("/") for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()}


def _origin_from_header(value: str) -> str:
    parsed = urlparse(value)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


class CSRFOriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE_METHODS and settings.SESSION_COOKIE_NAME in request.cookies:
            header_value = request.headers.get("origin") or request.headers.get("referer")
            if not header_value:
                return JSONResponse(status_code=403, content={"detail": "Missing Origin header for a state-changing request."})

            request_origin = _origin_from_header(header_value)
            if request_origin not in _allowed_origins():
                return JSONResponse(status_code=403, content={"detail": "Request origin is not allowed."})

        return await call_next(request)
