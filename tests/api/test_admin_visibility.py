#!/usr/bin/env python3
"""
Regression test: superuser org admins must see both admin screens.

When a user is both a superuser AND an org admin, the /account/me endpoint
must return:
  - is_superuser: true    → shows System Admin screen
  - organization_role: "admin" (lowercase) → shows Organization Admin screen

If organization_role is uppercase ("ADMIN") the frontend comparison
`=== 'admin'` fails and the org admin screen is hidden.

This test verifies:
1. A superuser who is an org admin gets both flags correctly.
2. organization_role is always lowercase in the /account/me response.
3. A non-superuser org admin sees org admin but not system admin.
4. A non-admin org member sees neither admin screen.
"""

import sys
import os
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_BASE_URL

BASE_URL = API_BASE_URL
UNIQUE = uuid.uuid4().hex[:8]

# admin@ex.com is both a superuser and an org admin in the "Ex" organization
SUPERUSER_ADMIN_EMAIL = "admin@ex.com"
SUPERUSER_ADMIN_PASSWORD = "admin123"


def login(email, password):
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login {email} failed: {resp.status_code} {resp.text}"
    return resp.json()


def get_account_me(token):
    resp = requests.get(
        f"{BASE_URL}/account/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, f"/account/me failed: {resp.status_code} {resp.text}"
    return resp.json()


def register(email, password, org_name):
    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password, "organization_name": org_name},
    )
    assert resp.status_code == 200, f"Register failed: {resp.status_code} {resp.text}"
    return resp.json()


def main():
    print("Admin Visibility Regression Test")
    print("=" * 60)

    # ---------------------------------------------------------------
    # Test 1: Superuser + org admin sees both screens
    # ---------------------------------------------------------------
    print("\n1. Superuser org admin gets both is_superuser and organization_role='admin'...")

    # Use admin@ex.com which is both a superuser and an org admin
    login_resp = login(SUPERUSER_ADMIN_EMAIL, SUPERUSER_ADMIN_PASSWORD)
    account = get_account_me(login_resp["access_token"])

    assert account["is_superuser"] is True, (
        f"Expected is_superuser=true for {SUPERUSER_ADMIN_EMAIL}, got {account['is_superuser']}"
    )
    assert account.get("organization_role") is not None, (
        f"organization_role is missing from /account/me for {SUPERUSER_ADMIN_EMAIL}"
    )
    assert account["organization_role"] == "admin", (
        f"REGRESSION: organization_role should be lowercase 'admin', "
        f"got '{account['organization_role']}'. "
        "The frontend org admin screen will NOT be shown."
    )
    print(f"   is_superuser={account['is_superuser']}, "
          f"organization_role='{account['organization_role']}' — CORRECT")

    # ---------------------------------------------------------------
    # Test 2: organization_role is always lowercase
    # ---------------------------------------------------------------
    print("\n2. Verifying organization_role is lowercase...")
    role = account["organization_role"]
    assert role == role.lower(), (
        f"REGRESSION: organization_role '{role}' is not lowercase. "
        "Frontend comparison === 'admin' will fail."
    )
    print(f"   organization_role='{role}' is lowercase — CORRECT")

    # ---------------------------------------------------------------
    # Test 3: Non-superuser org admin sees org admin but not system admin
    # ---------------------------------------------------------------
    print("\n3. Non-superuser org admin: org admin=yes, system admin=no...")
    reg_email = f"adminvis-admin-{UNIQUE}@example.com"
    reg_password = "testpassword123"
    register(reg_email, reg_password, f"AdminVis Test {UNIQUE}")

    admin_login = login(reg_email, reg_password)
    admin_account = get_account_me(admin_login["access_token"])

    assert admin_account["is_superuser"] is False, (
        f"Fresh registered user should not be superuser"
    )
    assert admin_account["organization_role"] == "admin", (
        f"Registered user should be org admin, got '{admin_account.get('organization_role')}'"
    )
    print(f"   is_superuser={admin_account['is_superuser']}, "
          f"organization_role='{admin_account['organization_role']}' — CORRECT")

    # ---------------------------------------------------------------
    # Test 4: Org member (non-admin) sees neither admin screen
    # ---------------------------------------------------------------
    print("\n4. Org member (non-admin): org admin=no, system admin=no...")
    member_email = f"adminvis-member-{UNIQUE}@example.com"
    member_password = "testpassword123"
    register(member_email, member_password, f"AdminVis Member Org {UNIQUE}")

    # Invite this member to the admin's org as "member" role
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
    invite_resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": member_email, "role": "member"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 200, (
        f"Invitation failed: {invite_resp.status_code} {invite_resp.text}"
    )
    invite_token = invite_resp.json()["token"]

    # Accept invitation as the member
    member_login = login(member_email, member_password)
    member_headers = {"Authorization": f"Bearer {member_login['access_token']}"}
    accept_resp = requests.post(
        f"{BASE_URL}/organizations/invitations/accept/{invite_token}",
        headers=member_headers,
    )
    assert accept_resp.status_code == 200, (
        f"Accept failed: {accept_resp.status_code} {accept_resp.text}"
    )

    # Switch to the admin's org
    admin_org_id = admin_account["organization_id"]
    switch_resp = requests.post(
        f"{BASE_URL}/organizations/switch/{admin_org_id}",
        headers=member_headers,
    )
    assert switch_resp.status_code == 200, (
        f"Switch failed: {switch_resp.status_code} {switch_resp.text}"
    )

    # Check /account/me with new token
    new_token = switch_resp.json()["access_token"]
    member_account = get_account_me(new_token)

    assert member_account["is_superuser"] is False, "Member should not be superuser"
    assert member_account["organization_role"] == "member", (
        f"Expected organization_role='member', got '{member_account.get('organization_role')}'"
    )
    assert member_account["organization_role"] == member_account["organization_role"].lower(), (
        f"organization_role '{member_account['organization_role']}' is not lowercase"
    )
    print(f"   is_superuser={member_account['is_superuser']}, "
          f"organization_role='{member_account['organization_role']}' — CORRECT")

    print("\n" + "=" * 60)
    print("PASSED: All admin visibility checks correct")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
