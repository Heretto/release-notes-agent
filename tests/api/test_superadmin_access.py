#!/usr/bin/env python3
"""
Tests that superadmin endpoints are restricted to superusers only.

Verifies that:
- Non-superuser accounts get 403 on all /superadmin/* endpoints
- Unauthenticated requests get 401 on all /superadmin/* endpoints
- Superuser accounts can access /superadmin/* endpoints (200)
"""

import sys
import os
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

BASE_URL = API_BASE_URL

# A second non-superuser test account. Created on-the-fly if needed.
NON_SUPER_EMAIL = f"nonsupertest-{uuid.uuid4().hex[:8]}@example.com"
NON_SUPER_PASSWORD = "testpassword123"


def get_auth_headers(email=TEST_EMAIL, password=TEST_PASSWORD):
    """Login and return authorization headers."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def ensure_non_superuser_account():
    """Register a fresh non-superuser account for testing."""
    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": NON_SUPER_EMAIL,
            "password": NON_SUPER_PASSWORD,
            "organization_name": f"Test Org {uuid.uuid4().hex[:6]}",
        }
    )
    if resp.status_code == 400 and "already registered" in resp.text.lower():
        return  # already exists
    assert resp.status_code == 200, f"Registration failed: {resp.status_code} {resp.text}"


# ---------------------------------------------------------------------------
# Superadmin endpoints under test
# ---------------------------------------------------------------------------
FAKE_ORG_ID = str(uuid.uuid4())
FAKE_USER_ID = str(uuid.uuid4())

SUPERADMIN_ENDPOINTS = [
    ("GET",  f"/superadmin/organizations"),
    ("GET",  f"/superadmin/organizations/{FAKE_ORG_ID}"),
    ("DELETE", f"/superadmin/organizations/{FAKE_ORG_ID}"),
    ("POST", f"/superadmin/organizations/{FAKE_ORG_ID}/members"),
    ("DELETE", f"/superadmin/organizations/{FAKE_ORG_ID}/members/{FAKE_USER_ID}"),
    ("POST", f"/superadmin/organizations/{FAKE_ORG_ID}/invitations"),
]


def test_unauthenticated_returns_401():
    """All superadmin endpoints must return 401 without a token."""
    print("\nTest: Unauthenticated requests get 401")
    print("-" * 40)

    for method, path in SUPERADMIN_ENDPOINTS:
        url = f"{BASE_URL}{path}"
        if method == "GET":
            resp = requests.get(url)
        elif method == "POST":
            resp = requests.post(url, json={})
        elif method == "DELETE":
            resp = requests.delete(url)
        else:
            raise ValueError(f"Unexpected method {method}")

        assert resp.status_code in (401, 403), (
            f"{method} {path} returned {resp.status_code}, expected 401/403"
        )
        print(f"  {method:6} {path:55} -> {resp.status_code}")

    print("  ✓ All unauthenticated requests rejected")
    return True


def test_non_superuser_returns_403(headers):
    """A regular (non-superuser) account must get 403 on every superadmin endpoint."""
    print("\nTest: Non-superuser gets 403")
    print("-" * 40)

    for method, path in SUPERADMIN_ENDPOINTS:
        url = f"{BASE_URL}{path}"
        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            resp = requests.post(url, json={"email": "x@x.com", "role": "member"}, headers=headers)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unexpected method {method}")

        assert resp.status_code == 403, (
            f"{method} {path} returned {resp.status_code}, expected 403 "
            f"(body: {resp.text[:200]})"
        )
        print(f"  {method:6} {path:55} -> {resp.status_code}")

    print("  ✓ All non-superuser requests forbidden")
    return True


def test_superuser_can_list_orgs(su_headers):
    """A superuser should be able to list organizations (200)."""
    print("\nTest: Superuser can access /superadmin/organizations")
    print("-" * 40)

    resp = requests.get(f"{BASE_URL}/superadmin/organizations", headers=su_headers)
    assert resp.status_code == 200, (
        f"Superuser list orgs returned {resp.status_code}, expected 200: {resp.text[:200]}"
    )
    orgs = resp.json()
    assert isinstance(orgs, list), "Expected a list of organizations"
    print(f"  ✓ Superuser got 200 with {len(orgs)} organization(s)")
    return True


def main():
    print("Superadmin Access Control Tests")
    print("=" * 60)

    # Prepare accounts
    ensure_non_superuser_account()
    non_su_headers = get_auth_headers(NON_SUPER_EMAIL, NON_SUPER_PASSWORD)
    su_headers = get_auth_headers(TEST_EMAIL, TEST_PASSWORD)
    print("✓ Authenticated (superuser + non-superuser)")

    results = []
    results.append(("Unauthenticated → 401", test_unauthenticated_returns_401()))
    results.append(("Non-superuser → 403",   test_non_superuser_returns_403(non_su_headers)))
    results.append(("Superuser → 200",       test_superuser_can_list_orgs(su_headers)))

    print("\n" + "=" * 60)
    all_passed = True
    for name, passed in results:
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ All superadmin access control tests passed!")
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
