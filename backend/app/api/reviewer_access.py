"""Keep reviewers inside the review UI.

A reviewer may read a release's notes, comment on them and say they have read them. They
may not write notes, run releases, configure instruction sets, manage credentials or agents,
or administer the organization.

Enforced as middleware rather than a dependency on each route because most of the routes a
reviewer must not reach are **hop-core's** — credentials, agents, organizations, admin — and
this app cannot add dependencies to routers it does not own. A whitelist is also the safer
shape: a route added later is closed until someone deliberately opens it, which is the right
default for an access rule.

The allowed set is deliberately small and written out in full below. Everything under the
API prefix that is not on it is refused with 403 and `code: "reviewer_only"`, which is what
the browser uses to send the person to the request-promotion screen.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Pattern, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from hop_core.core.security import decode_token
from hop_core.db import get_session_factory

from app.models.database import AppRole
from app.services.app_roles import role_for

logger = logging.getLogger(__name__)

_UUID = r"[0-9a-fA-F-]{36}"


def _rule(methods: str, path: str) -> Tuple[List[str], Pattern[str]]:
    return methods.split(), re.compile(f"^{path}$")


#: What a reviewer may reach, as (methods, path regex) against the path *after* the API
#: prefix. Anything not listed is refused.
REVIEWER_ROUTES: List[Tuple[List[str], Pattern[str]]] = [
    # Signing in, signing out, refreshing, and the SSO round trip.
    _rule("GET POST PUT PATCH DELETE OPTIONS", r"/auth(/.*)?"),
    # Their own account: password, name, sign-out of other sessions.
    _rule("GET POST PATCH PUT", r"/account(/.*)?"),
    # The shell needs to know which organization it is in to boot.
    _rule("GET", r"/organizations"),
    _rule("GET", r"/organizations/current"),
    # Their own app role, which is how the browser knows to show the review UI.
    _rule("GET", r"/people/me"),
    # The release being reviewed, and its notes.
    _rule("GET", rf"/jobs/{_UUID}"),
    _rule("GET", rf"/jobs/{_UUID}/items"),
    _rule("GET", rf"/jobs/{_UUID}/items/{_UUID}"),
    # Marking a note read. The route itself refuses every other field from a reviewer.
    _rule("PATCH", rf"/jobs/{_UUID}/items/{_UUID}"),
    # Comments: read, add, resolve.
    _rule("GET POST", rf"/jobs/{_UUID}/items/{_UUID}/comments"),
    _rule("PATCH", rf"/jobs/{_UUID}/items/{_UUID}/comments/{_UUID}"),
]


#: The role lookup sits on every authenticated request that is not on the whitelist — which
#: is most of an author's traffic — so it is cached briefly rather than queried every time.
#: A promotion therefore takes effect within this many seconds rather than instantly; the
#: routes themselves read the role fresh, so only this gate is ever stale.
_ROLE_TTL_SECONDS = 30
_role_cache: Dict[Tuple[str, str], Tuple[float, str]] = {}


def _cached_role(db, organization_id: str, email: str) -> str:
    key = (str(organization_id), email.lower())
    hit = _role_cache.get(key)
    now = time.monotonic()
    if hit and hit[0] > now:
        return hit[1]
    role = role_for(db, organization_id, email)
    _role_cache[key] = (now + _ROLE_TTL_SECONDS, role)
    return role


def forget_cached_roles() -> None:
    """Drop the gate's cache — called when a role changes so it takes effect at once."""
    _role_cache.clear()


def reviewer_may(method: str, path: str) -> bool:
    """Is this request on the reviewer whitelist?"""
    return any(method in methods and pattern.match(path) for methods, pattern in REVIEWER_ROUTES)


class ReviewerAccessMiddleware(BaseHTTPMiddleware):
    """Refuse anything outside the review UI when the caller is a reviewer.

    Reads the caller's email and organization from the access token rather than loading the
    user, so the only database work is the role lookup itself. An unauthenticated or
    unreadable request is passed straight through — deciding what to do about *that* is the
    job of the route's own authentication, which gives a much better error than this can.
    """

    def __init__(self, app, api_prefix: str):
        super().__init__(app)
        self.api_prefix = api_prefix.rstrip("/")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(self.api_prefix + "/"):
            return await call_next(request)

        claims = self._claims(request)
        if claims is None:
            return await call_next(request)

        email, organization_id = claims
        relative = path[len(self.api_prefix):]
        if reviewer_may(request.method, relative):
            return await call_next(request)

        session_factory = get_session_factory()
        db = session_factory()
        try:
            if _cached_role(db, organization_id, email) != AppRole.REVIEWER:
                return await call_next(request)
        finally:
            db.close()

        logger.info("Reviewer %s refused %s %s", email, request.method, relative)
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "code": "reviewer_only",
                    "message": (
                        "Your account can review release notes but not edit them. "
                        "Ask an administrator to make you an author."
                    ),
                }
            },
        )

    @staticmethod
    def _claims(request: Request):
        """(email, organization_id) from the access token, or None if there isn't one."""
        header = request.headers.get("authorization") or ""
        token = header[7:].strip() if header.lower().startswith("bearer ") else None
        if not token:
            token = request.cookies.get("access_token")
        if not token:
            return None
        try:
            payload = decode_token(token)
        except Exception:  # noqa: BLE001 — an unreadable token is the route's problem, not ours
            return None
        if payload.get("type") != "access":
            return None
        email = payload.get("email")
        organization_id = payload.get("org_id")
        if not email or not organization_id:
            return None
        return email, organization_id
