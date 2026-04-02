"""CSRF protection middleware using the double-submit cookie pattern.

State-changing requests (POST, PUT, DELETE, PATCH) that carry an
access_token cookie must also include an ``X-CSRF-Token`` header whose
value matches the ``csrf_token`` cookie set at login.

Requests authenticated via the ``Authorization`` header (API clients,
tests) are exempt because they are not vulnerable to CSRF — the browser
never attaches that header automatically.
"""

import hmac
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS:
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
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token missing or invalid"},
            )

        return await call_next(request)
