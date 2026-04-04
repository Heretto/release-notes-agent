"""CSRF protection middleware using the double-submit cookie pattern.

State-changing requests (POST, PUT, DELETE, PATCH) that carry an
access_token cookie must also include an ``X-CSRF-Token`` header whose
value matches the ``csrf_token`` cookie set at login.

Requests authenticated via the ``Authorization`` header (API clients,
tests) are exempt because they are not vulnerable to CSRF — the browser
never attaches that header automatically.

Auth endpoints (login, register, refresh, logout) are also exempt:
- login / register create a session, they don't act on one, so there is
  nothing for CSRF to protect.  Enforcing CSRF here creates a deadlock:
  a stale access_token cookie (e.g. from a previous session) would block
  login because the browser sends the old cookie but JS can no longer read
  the old csrf_token to include as a header.
- refresh / logout are token-management operations where the CSRF token
  itself may be expired or unavailable.
"""

import hmac
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths exempt from CSRF regardless of cookies present.
# These are authentication endpoints that establish or tear down sessions
# rather than acting on an existing authenticated session.
_CSRF_EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
})


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        # Auth endpoints are exempt — see module docstring.
        if request.url.path in _CSRF_EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF check when the client authenticates via Authorization header
        # (not browser-based, so not susceptible to CSRF).
        if request.headers.get("authorization"):
            return await call_next(request)

        # Only enforce when the browser is sending an access_token cookie
        # (i.e. a cookie-authenticated session).
        if "access_token" not in request.cookies:
            return await call_next(request)

        csrf_cookie = request.cookies.get("csrf_token", "")
        csrf_header = request.headers.get("x-csrf-token", "")

        if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
            # Must return a Response directly — raising HTTPException inside
            # BaseHTTPMiddleware bypasses FastAPI's exception handlers and
            # causes uvicorn to log an unhandled exception (500).
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"},
            )

        return await call_next(request)
