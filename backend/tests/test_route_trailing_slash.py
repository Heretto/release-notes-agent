"""
Regression tests for trailing-slash redirect behaviour.

After setting redirect_slashes=False on the FastAPI app, every collection
endpoint must respond to the *no-slash* URL (e.g. GET /api/v1/jobs) with a
2xx status, NOT with a 307 redirect.  The Angular frontend and the integration
test suite call these URLs without trailing slashes; a 307 sends the browser
to http://localhost/api/v1/jobs/ (port 80) which is unreachable.

These tests hit the real TestClient (no real DB required for the 2xx check)
and confirm:
  1. The no-slash URL returns 200 or 401 (not 307 / 404).
  2. The trailing-slash URL returns 404 (redirect_slashes=False, so we don't
     silently re-enable redirects in the future).
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

# Collection endpoints that Angular and tests call without trailing slash.
# They require auth, so we expect 401 — but NOT 307 or 404.
COLLECTION_ENDPOINTS = [
    "/api/v1/jobs",
    "/api/v1/instructions",
    "/api/v1/credentials",
    "/api/v1/webhooks",
    "/api/v1/organizations",
]


@pytest.mark.parametrize("path", COLLECTION_ENDPOINTS)
def test_no_slash_returns_non_redirect(path):
    """No-trailing-slash URL must not return 307 or 404."""
    resp = client.get(path)
    assert resp.status_code not in (307, 404), (
        f"GET {path} returned {resp.status_code}. "
        "Expected 200/401/403, not a redirect or 404. "
        "Ensure redirect_slashes=False is set and the route uses '' not '/'."
    )


@pytest.mark.parametrize("path", COLLECTION_ENDPOINTS)
def test_trailing_slash_returns_404(path):
    """Trailing-slash URL must return 404 (redirect_slashes=False is active)."""
    resp = client.get(path + "/")
    assert resp.status_code == 404, (
        f"GET {path}/ returned {resp.status_code} instead of 404. "
        "If this is 307, redirect_slashes has been re-enabled. "
        "If this is 200/401, a duplicate route with '/' was accidentally added."
    )
