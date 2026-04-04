"""
Unit tests for CSRFMiddleware.

Covers:
- Safe methods (GET/HEAD/OPTIONS) are always passed through
- POST/PUT/DELETE/PATCH with Authorization header skip CSRF (Bearer-token clients)
- Cookie-authenticated requests without access_token cookie skip CSRF
- Cookie-authenticated requests with mismatched CSRF token get 403
- Cookie-authenticated requests with missing CSRF cookie get 403
- Cookie-authenticated requests with missing CSRF header get 403
- Cookie-authenticated requests with matching CSRF token pass through

Regression guard:
- CSRF rejection MUST return a proper HTTP response (not raise an exception),
  because raising HTTPException inside BaseHTTPMiddleware bypasses FastAPI's
  exception handlers and causes uvicorn to emit a 500 Internal Server Error.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.csrf import CSRFMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app() -> FastAPI:
    """Minimal FastAPI app wrapped in CSRFMiddleware."""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.get("/resource")
    async def get_resource():
        return {"ok": True}

    @app.post("/resource")
    async def post_resource():
        return {"ok": True}

    @app.put("/resource")
    async def put_resource():
        return {"ok": True}

    @app.delete("/resource")
    async def delete_resource():
        return {"ok": True}

    @app.patch("/resource")
    async def patch_resource():
        return {"ok": True}

    return app


@pytest.fixture(scope="module")
def client():
    return TestClient(_build_app(), raise_server_exceptions=False)


TOKEN = "abc123"


def _build_app_with_auth_routes() -> FastAPI:
    """App that also has auth-path routes for testing the exemption."""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/resource")
    async def post_resource():
        return {"ok": True}

    for path in ["/api/v1/auth/login", "/api/v1/auth/register",
                 "/api/v1/auth/refresh", "/api/v1/auth/logout"]:
        # FastAPI needs unique function names per route
        async def auth_handler():
            return {"ok": True}
        app.post(path)(auth_handler)

    return app


@pytest.fixture(scope="module")
def auth_client():
    return TestClient(_build_app_with_auth_routes(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Safe methods always pass through
# ---------------------------------------------------------------------------

class TestSafeMethods:
    def test_get_passes_without_any_csrf(self, client):
        resp = client.get("/resource", cookies={"access_token": TOKEN})
        assert resp.status_code == 200

    def test_head_passes_without_any_csrf(self, client):
        # HEAD has no route defined → 405, but must not be a 403 CSRF rejection
        resp = client.head("/resource", cookies={"access_token": TOKEN})
        assert resp.status_code != 403

    def test_options_passes_without_any_csrf(self, client):
        # OPTIONS has no route defined → 405, but must not be a 403 CSRF rejection
        resp = client.options("/resource", cookies={"access_token": TOKEN})
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Authorization header exemption (Bearer token / API clients)
# ---------------------------------------------------------------------------

class TestBearerTokenExemption:
    def test_post_with_authorization_header_passes(self, client):
        resp = client.post(
            "/resource",
            headers={"Authorization": "Bearer some-token"},
            cookies={"access_token": TOKEN},
        )
        assert resp.status_code == 200

    def test_delete_with_authorization_header_passes(self, client):
        resp = client.delete(
            "/resource",
            headers={"Authorization": "Bearer some-token"},
        )
        assert resp.status_code == 200

    def test_put_with_authorization_header_passes(self, client):
        resp = client.put(
            "/resource",
            headers={"Authorization": "Bearer some-token"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# No access_token cookie — CSRF is not enforced
# ---------------------------------------------------------------------------

class TestNoCookieSession:
    def test_post_without_access_token_cookie_passes(self, client):
        """Requests without access_token cookie are not cookie-auth'd; skip CSRF."""
        resp = client.post("/resource")
        assert resp.status_code == 200

    def test_post_with_only_csrf_cookie_passes(self, client):
        """access_token absent → middleware skips enforcement regardless of csrf_token."""
        resp = client.post(
            "/resource",
            cookies={"csrf_token": "some-token"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cookie-authenticated requests — CSRF IS enforced
# ---------------------------------------------------------------------------

class TestCookieAuthCSRFEnforcement:
    def test_post_with_matching_csrf_passes(self, client):
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "secret"},
            headers={"X-CSRF-Token": "secret"},
        )
        assert resp.status_code == 200

    def test_put_with_matching_csrf_passes(self, client):
        resp = client.put(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "secret"},
            headers={"X-CSRF-Token": "secret"},
        )
        assert resp.status_code == 200

    def test_delete_with_matching_csrf_passes(self, client):
        resp = client.delete(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "secret"},
            headers={"X-CSRF-Token": "secret"},
        )
        assert resp.status_code == 200

    def test_patch_with_matching_csrf_passes(self, client):
        resp = client.patch(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "secret"},
            headers={"X-CSRF-Token": "secret"},
        )
        assert resp.status_code == 200

    def test_post_with_mismatched_csrf_returns_403(self, client):
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "cookie-value"},
            headers={"X-CSRF-Token": "different-value"},
        )
        assert resp.status_code == 403

    def test_post_with_missing_csrf_header_returns_403(self, client):
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "secret"},
            # No X-CSRF-Token header
        )
        assert resp.status_code == 403

    def test_post_with_missing_csrf_cookie_returns_403(self, client):
        """csrf_token cookie absent even though access_token is present."""
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN},
            headers={"X-CSRF-Token": "secret"},
        )
        assert resp.status_code == 403

    def test_post_with_no_csrf_at_all_returns_403(self, client):
        """Cookie-authenticated session with neither csrf cookie nor header."""
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN},
        )
        assert resp.status_code == 403

    def test_403_response_is_json(self, client):
        """CSRF rejection must return a JSON body, not an HTML error page."""
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN},
        )
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json() == {"detail": "CSRF token missing or invalid"}


# ---------------------------------------------------------------------------
# Auth endpoint exemption
# ---------------------------------------------------------------------------

class TestAuthEndpointExemption:
    """
    login / register / refresh / logout must be exempt from CSRF even when an
    access_token cookie is present.

    Rationale: these endpoints create or destroy sessions rather than acting on
    one.  Enforcing CSRF on login causes a deadlock when the user has a stale
    access_token cookie — the browser sends it automatically, triggering
    enforcement, but JS cannot supply a valid X-CSRF-Token because there is no
    active session to read the cookie from.
    """

    def test_login_passes_with_stale_access_token_and_no_csrf(self, auth_client):
        """Primary regression: stale cookie must not block login."""
        resp = auth_client.post(
            "/api/v1/auth/login",
            cookies={"access_token": TOKEN},  # stale — no csrf_token present
        )
        assert resp.status_code == 200, (
            "Login must succeed even when a stale access_token cookie is present "
            "and no X-CSRF-Token header is sent."
        )

    def test_register_passes_without_csrf(self, auth_client):
        resp = auth_client.post("/api/v1/auth/register")
        assert resp.status_code == 200

    def test_refresh_passes_with_cookie_and_no_csrf(self, auth_client):
        resp = auth_client.post(
            "/api/v1/auth/refresh",
            cookies={"access_token": TOKEN},
        )
        assert resp.status_code == 200

    def test_logout_passes_with_cookie_and_no_csrf(self, auth_client):
        resp = auth_client.post(
            "/api/v1/auth/logout",
            cookies={"access_token": TOKEN},
        )
        assert resp.status_code == 200

    def test_non_auth_post_is_still_enforced(self, auth_client):
        """Exemption must be path-specific — other cookie-auth'd POSTs still need CSRF."""
        resp = auth_client.post(
            "/resource",
            cookies={"access_token": TOKEN},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Regression: csrf_token cookie path must be "/" not "/api/v1"
# ---------------------------------------------------------------------------

class TestCSRFCookiePath:
    """
    Regression guard for the cookie-path bug that caused 403s on instruction-set
    creation (and all other state-changing requests from the Angular frontend).

    Root cause: csrf_token was set with path="/api/v1".  document.cookie only
    exposes a cookie to JavaScript when the current page path starts with the
    cookie's path.  Since the Angular SPA lives at paths like /instructions,
    getCookie('csrf_token') returned null, no X-CSRF-Token header was sent, and
    the CSRF middleware correctly (but unexpectedly) rejected the request.

    Fix: csrf_token must use path="/" so it is readable from every SPA route.
    The access_token can keep path="/api/v1" because it is HttpOnly and only
    needs to be sent automatically by the browser on API calls.
    """

    def test_csrf_token_cookie_path_is_root(self):
        """set_auth_cookies must set csrf_token with path='/'."""
        from unittest.mock import MagicMock
        from app.core.security import set_auth_cookies

        response = MagicMock()
        set_auth_cookies(response, access_token="at", refresh_token="rt")

        calls = {
            call.kwargs["key"]: call.kwargs
            for call in response.set_cookie.call_args_list
        }

        assert "csrf_token" in calls, "csrf_token cookie was not set"
        csrf_path = calls["csrf_token"].get("path")
        assert csrf_path == "/", (
            f"csrf_token path must be '/' so JavaScript on any SPA route can "
            f"read it via document.cookie. Got: {csrf_path!r}"
        )

    def test_access_token_cookie_path_is_api(self):
        """access_token should keep path='/api/v1' (HttpOnly, browser-only)."""
        from unittest.mock import MagicMock
        from app.core.security import set_auth_cookies

        response = MagicMock()
        set_auth_cookies(response, access_token="at", refresh_token="rt")

        calls = {
            call.kwargs["key"]: call.kwargs
            for call in response.set_cookie.call_args_list
        }

        assert calls["access_token"].get("path") == "/api/v1"

    def test_clear_auth_cookies_uses_root_path_for_csrf(self):
        """clear_auth_cookies must delete csrf_token with path='/' to actually clear it."""
        from unittest.mock import MagicMock
        from app.core.security import clear_auth_cookies

        response = MagicMock()
        clear_auth_cookies(response)

        calls = {
            call.kwargs["key"]: call.kwargs
            for call in response.delete_cookie.call_args_list
        }

        assert "csrf_token" in calls, "csrf_token was not deleted"
        assert calls["csrf_token"].get("path") == "/", (
            "delete_cookie path must match set_cookie path, otherwise the "
            "browser ignores the deletion and the stale cookie persists."
        )


# ---------------------------------------------------------------------------
# Regression guard: must not produce 500
# ---------------------------------------------------------------------------

class TestNoInternalServerError:
    """
    Before the fix, CSRFMiddleware raised HTTPException inside
    BaseHTTPMiddleware.  Starlette does not catch FastAPI's HTTPException in
    middleware, so uvicorn logged an unhandled exception and returned 500.
    The fix returns a JSONResponse directly.  These tests verify that CSRF
    failures always produce a 4xx, never a 5xx.
    """

    def test_mismatched_token_is_not_500(self, client):
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "a"},
            headers={"X-CSRF-Token": "b"},
        )
        assert resp.status_code < 500

    def test_missing_header_is_not_500(self, client):
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN, "csrf_token": "secret"},
        )
        assert resp.status_code < 500

    def test_missing_cookie_is_not_500(self, client):
        resp = client.post(
            "/resource",
            cookies={"access_token": TOKEN},
            headers={"X-CSRF-Token": "secret"},
        )
        assert resp.status_code < 500
