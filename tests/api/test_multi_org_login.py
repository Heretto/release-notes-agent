#!/usr/bin/env python3
"""
Regression test: multi-org users must receive the organizations list on login.

When a user belongs to more than one organization, the login response MUST
include an `organizations` array with length > 1 so the frontend can show
the organization selector.

This test:
1. Creates two fresh organizations (each with its own admin via /register).
2. Invites the first user to the second organization.
3. The first user accepts the invitation.
4. Logs in as the first user and verifies `organizations` contains both orgs.
"""

import sys
import os
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_BASE_URL

BASE_URL = API_BASE_URL
UNIQUE = uuid.uuid4().hex[:8]

USER_A_EMAIL = f"multiorg-a-{UNIQUE}@example.com"
USER_A_PASSWORD = "testpassword123"
ORG_A_NAME = f"Multi Org A {UNIQUE}"

USER_B_EMAIL = f"multiorg-b-{UNIQUE}@example.com"
USER_B_PASSWORD = "testpassword123"
ORG_B_NAME = f"Multi Org B {UNIQUE}"


def register(email, password, org_name):
    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "organization_name": org_name},
    )
    assert resp.status_code == 200, f"Register {email} failed: {resp.status_code} {resp.text}"
    return resp.json()


def login(email, password):
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login {email} failed: {resp.status_code} {resp.text}"
    return resp.json()


def headers_from(login_resp):
    return {"Authorization": f"Bearer {login_resp['access_token']}"}


def main():
    print("Multi-Org Login Regression Test")
    print("=" * 60)

    # 1. Register two users, each with their own org
    print("\n1. Registering two users with separate organizations...")
    register(USER_A_EMAIL, USER_A_PASSWORD, ORG_A_NAME)
    register(USER_B_EMAIL, USER_B_PASSWORD, ORG_B_NAME)
    print(f"   Registered {USER_A_EMAIL} (org: {ORG_A_NAME})")
    print(f"   Registered {USER_B_EMAIL} (org: {ORG_B_NAME})")

    # 2. Login as user B (admin of org B) and invite user A
    print("\n2. User B invites User A to Org B...")
    b_login = login(USER_B_EMAIL, USER_B_PASSWORD)
    b_headers = headers_from(b_login)

    invite_resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": USER_A_EMAIL, "role": "member"},
        headers=b_headers,
    )
    assert invite_resp.status_code == 200, (
        f"Invitation failed: {invite_resp.status_code} {invite_resp.text}"
    )
    invite_token = invite_resp.json()["token"]
    print(f"   Invitation created (token: {invite_token[:12]}...)")

    # 3. Login as user A and accept the invitation
    print("\n3. User A accepts the invitation...")
    a_login = login(USER_A_EMAIL, USER_A_PASSWORD)
    a_headers = headers_from(a_login)

    accept_resp = requests.post(
        f"{BASE_URL}/organizations/invitations/accept/{invite_token}",
        headers=a_headers,
    )
    assert accept_resp.status_code == 200, (
        f"Accept failed: {accept_resp.status_code} {accept_resp.text}"
    )
    print("   Invitation accepted")

    # 4. Login again as user A and verify the organizations list
    print("\n4. Verifying login response contains multiple organizations...")
    a_login2 = login(USER_A_EMAIL, USER_A_PASSWORD)
    orgs = a_login2.get("organizations")

    assert orgs is not None, "Login response missing 'organizations' field"
    assert isinstance(orgs, list), f"Expected list, got {type(orgs)}"
    assert len(orgs) >= 2, (
        f"REGRESSION: User belongs to 2+ orgs but login returned {len(orgs)} org(s): "
        f"{[o.get('name') for o in orgs]}. "
        "The frontend org selector will NOT be shown."
    )

    org_names = [o["name"] for o in orgs]
    print(f"   Login returned {len(orgs)} organizations: {org_names}")

    assert ORG_A_NAME in org_names, f"Missing user's own org '{ORG_A_NAME}' in {org_names}"
    assert ORG_B_NAME in org_names, f"Missing invited org '{ORG_B_NAME}' in {org_names}"

    # 5. Verify each org entry has required fields
    print("\n5. Verifying organization entry fields...")
    for org in orgs:
        for field in ("id", "name", "slug", "role"):
            assert field in org, f"Missing field '{field}' in org entry: {org}"
        assert org["role"] in ("admin", "member"), (
            f"Role should be lowercase 'admin' or 'member', got '{org['role']}'"
        )
    print("   All org entries have correct fields and lowercase roles")

    print("\n" + "=" * 60)
    print("PASSED: Multi-org users receive the full organizations list on login")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
