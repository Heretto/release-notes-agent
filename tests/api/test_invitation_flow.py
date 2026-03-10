#!/usr/bin/env python3
"""
End-to-end test for the user invitation flow.

Verifies the full lifecycle:
1. Admin creates an invitation for a new email
2. Invitation appears in the pending invitations list
3. Duplicate invitation is rejected
4. Invited user registers an account
5. Invited user accepts the invitation via token
6. User is now a member of the inviting organization
7. Accepting the same invitation again is rejected
8. Wrong user cannot accept another user's invitation
9. Admin can cancel a pending invitation
10. Non-admin cannot create invitations
"""

import sys
import os
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

BASE_URL = API_BASE_URL

# Unique emails for this test run
RUN_ID = uuid.uuid4().hex[:8]
ADMIN_EMAIL = f"orgadmin-{RUN_ID}@example.com"
ADMIN_PASSWORD = "testpassword123"
ADMIN_ORG_NAME = f"InviteTestOrg-{RUN_ID}"
INVITEE_EMAIL = f"invitee-{RUN_ID}@example.com"
INVITEE_PASSWORD = "testpassword123"
WRONG_USER_EMAIL = f"wronguser-{RUN_ID}@example.com"
WRONG_USER_PASSWORD = "testpassword123"


def get_auth_headers(email=TEST_EMAIL, password=TEST_PASSWORD):
    """Login and return authorization headers."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def register_user(email, password, org_name=None):
    """Register a new user account."""
    resp = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "password": password,
            "organization_name": org_name or f"Org-{uuid.uuid4().hex[:6]}",
        }
    )
    assert resp.status_code == 200, f"Registration failed for {email}: {resp.status_code} {resp.text}"
    return resp.json()


def test_create_invitation(admin_headers):
    """Admin creates an invitation and gets back a token."""
    print("\nTest: Admin creates an invitation")
    print("-" * 40)

    resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": INVITEE_EMAIL, "role": "member"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"Create invitation failed: {resp.status_code} {resp.text}"

    data = resp.json()
    assert data["email"] == INVITEE_EMAIL
    assert data["role"] == "member"
    assert data["token"], "Invitation token must not be empty"
    assert data["id"], "Invitation ID must not be empty"
    assert data["expires_at"], "Expiry must be set"

    print(f"  Invitation ID: {data['id']}")
    print(f"  Token: {data['token'][:16]}...")
    print(f"  Expires: {data['expires_at']}")
    print("  ✓ Invitation created successfully")
    return data


def test_invitation_appears_in_list(admin_headers, invitation_id):
    """The new invitation shows up in the pending list."""
    print("\nTest: Invitation appears in pending list")
    print("-" * 40)

    resp = requests.get(
        f"{BASE_URL}/organizations/invitations",
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"List invitations failed: {resp.status_code}"
    invitations = resp.json()

    found = any(inv["id"] == invitation_id for inv in invitations)
    assert found, f"Invitation {invitation_id} not found in pending list"

    print(f"  Found invitation in list ({len(invitations)} total pending)")
    print("  ✓ Invitation listed correctly")
    return True


def test_duplicate_invitation_rejected(admin_headers):
    """Creating a second invitation for the same email is rejected."""
    print("\nTest: Duplicate invitation is rejected")
    print("-" * 40)

    resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": INVITEE_EMAIL, "role": "member"},
        headers=admin_headers,
    )
    assert resp.status_code == 400, (
        f"Expected 400 for duplicate, got {resp.status_code}: {resp.text}"
    )
    assert "already" in resp.json().get("detail", "").lower()

    print(f"  Correctly rejected: {resp.json()['detail']}")
    print("  ✓ Duplicate invitation blocked")
    return True


def test_accept_invitation(invite_token):
    """Invited user registers and accepts the invitation."""
    print("\nTest: Invited user registers and accepts invitation")
    print("-" * 40)

    # Register the invitee
    register_user(INVITEE_EMAIL, INVITEE_PASSWORD)
    print(f"  Registered {INVITEE_EMAIL}")

    # Login as invitee
    invitee_headers = get_auth_headers(INVITEE_EMAIL, INVITEE_PASSWORD)

    # Accept the invitation
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations/accept/{invite_token}",
        json={},
        headers=invitee_headers,
    )
    assert resp.status_code == 200, (
        f"Accept invitation failed: {resp.status_code} {resp.text}"
    )
    assert "joined" in resp.json().get("message", "").lower() or "success" in resp.json().get("message", "").lower()

    print(f"  Response: {resp.json()['message']}")
    print("  ✓ Invitation accepted successfully")
    return True


def test_invitee_is_member(admin_headers):
    """After accepting, the invitee appears in the org members list."""
    print("\nTest: Invitee is now a member of the organization")
    print("-" * 40)

    resp = requests.get(
        f"{BASE_URL}/organizations/current/members",
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"List members failed: {resp.status_code}"
    members = resp.json()

    emails = [m["user_email"] for m in members]
    assert INVITEE_EMAIL in emails, (
        f"{INVITEE_EMAIL} not found in members: {emails}"
    )

    invitee_member = next(m for m in members if m["user_email"] == INVITEE_EMAIL)
    assert invitee_member["role"] == "member"

    print(f"  Found {INVITEE_EMAIL} in members list with role=member")
    print("  ✓ Invitee is a member")
    return True


def test_accept_again_rejected(invite_token):
    """Accepting an already-accepted invitation is rejected."""
    print("\nTest: Re-accepting invitation is rejected")
    print("-" * 40)

    invitee_headers = get_auth_headers(INVITEE_EMAIL, INVITEE_PASSWORD)
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations/accept/{invite_token}",
        json={},
        headers=invitee_headers,
    )
    # Should be 400 (already a member) or 404 (invitation already accepted)
    assert resp.status_code in (400, 404), (
        f"Expected 400/404, got {resp.status_code}: {resp.text}"
    )

    print(f"  Correctly rejected with {resp.status_code}: {resp.json().get('detail', '')}")
    print("  ✓ Double-accept blocked")
    return True


def test_wrong_user_cannot_accept(admin_headers):
    """A different user cannot accept an invitation addressed to someone else."""
    print("\nTest: Wrong user cannot accept another user's invitation")
    print("-" * 40)

    # Create a new invitation for a different email
    other_email = f"other-{RUN_ID}@example.com"
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": other_email, "role": "member"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"Create invitation failed: {resp.status_code}"
    other_token = resp.json()["token"]
    other_invite_id = resp.json()["id"]

    # Register the wrong user
    register_user(WRONG_USER_EMAIL, WRONG_USER_PASSWORD)
    wrong_headers = get_auth_headers(WRONG_USER_EMAIL, WRONG_USER_PASSWORD)

    # Try to accept the invitation meant for other_email
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations/accept/{other_token}",
        json={},
        headers=wrong_headers,
    )
    assert resp.status_code == 403, (
        f"Expected 403, got {resp.status_code}: {resp.text}"
    )

    print(f"  Correctly rejected: {resp.json().get('detail', '')}")

    # Clean up: cancel the unused invitation
    requests.delete(
        f"{BASE_URL}/organizations/invitations/{other_invite_id}",
        headers=admin_headers,
    )

    print("  ✓ Wrong user blocked from accepting")
    return True


def test_cancel_invitation(admin_headers):
    """Admin can cancel a pending invitation."""
    print("\nTest: Admin cancels a pending invitation")
    print("-" * 40)

    # Create an invitation to cancel
    cancel_email = f"cancel-{RUN_ID}@example.com"
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": cancel_email, "role": "member"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    invite_id = resp.json()["id"]
    invite_token = resp.json()["token"]
    print(f"  Created invitation {invite_id} for {cancel_email}")

    # Cancel it
    resp = requests.delete(
        f"{BASE_URL}/organizations/invitations/{invite_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"Cancel failed: {resp.status_code} {resp.text}"
    print(f"  Cancelled invitation: {resp.json()['message']}")

    # Verify it's no longer in the pending list
    resp = requests.get(
        f"{BASE_URL}/organizations/invitations",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    remaining_ids = [inv["id"] for inv in resp.json()]
    assert invite_id not in remaining_ids, "Cancelled invitation still in list"
    print("  Invitation removed from pending list")

    # Verify the token can no longer be accepted
    register_user(cancel_email, "testpassword123")
    cancel_headers = get_auth_headers(cancel_email, "testpassword123")
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations/accept/{invite_token}",
        json={},
        headers=cancel_headers,
    )
    assert resp.status_code == 404, (
        f"Expected 404 for cancelled token, got {resp.status_code}"
    )
    print("  Cancelled token correctly rejected (404)")
    print("  ✓ Invitation cancellation works")
    return True


def test_invitation_cannot_overwrite_password(admin_headers):
    """Security: accepting an invitation must NOT overwrite an existing user's password."""
    print("\nTest: Invitation cannot overwrite existing user's password")
    print("-" * 40)

    # Create an invitation for the invitee who already has an account
    victim_email = f"victim-{RUN_ID}@example.com"
    victim_password = "original-password-123"
    register_user(victim_email, victim_password)
    print(f"  Registered {victim_email}")

    # Admin creates invitation for the victim's email
    resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": victim_email, "role": "member"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"Create invitation failed: {resp.status_code}"
    invite_token = resp.json()["token"]
    invite_id = resp.json()["id"]

    # Attacker tries to use the new-user endpoint to set a new password
    attacker_password = "attacker-password-999"
    resp = requests.post(
        f"{BASE_URL}/invitations/accept/{invite_token}",
        json={"password": attacker_password, "confirm_password": attacker_password},
    )
    assert resp.status_code == 409, (
        f"Expected 409 (existing user), got {resp.status_code}: {resp.text}"
    )
    print(f"  New-user endpoint correctly rejected with 409")

    # Verify original password still works
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": victim_email, "password": victim_password},
    )
    assert login_resp.status_code == 200, (
        "SECURITY FAILURE: original password no longer works — it was overwritten!"
    )
    print(f"  Original password still works")

    # Verify attacker's password does NOT work
    bad_login = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": victim_email, "password": attacker_password},
    )
    assert bad_login.status_code != 200, (
        "SECURITY FAILURE: attacker's password works — password was overwritten!"
    )
    print(f"  Attacker's password correctly rejected")

    # Clean up
    requests.delete(
        f"{BASE_URL}/organizations/invitations/{invite_id}",
        headers=admin_headers,
    )

    print("  ✓ Password overwrite attack blocked")
    return True


def test_non_admin_cannot_invite():
    """A non-admin member cannot create invitations."""
    print("\nTest: Non-admin cannot create invitations")
    print("-" * 40)

    # The invitee we added earlier is a 'member', not 'admin'
    invitee_headers = get_auth_headers(INVITEE_EMAIL, INVITEE_PASSWORD)

    # Switch to the admin's organization first
    # List the invitee's orgs and find the admin's org
    resp = requests.get(f"{BASE_URL}/organizations", headers=invitee_headers)
    assert resp.status_code == 200
    orgs = resp.json()

    # Find the admin's org
    admin_headers = get_auth_headers(ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_resp = requests.get(f"{BASE_URL}/organizations/current", headers=admin_headers)
    admin_org_id = admin_resp.json()["id"]

    # Switch invitee to the admin's org
    switch_resp = requests.post(
        f"{BASE_URL}/organizations/switch/{admin_org_id}",
        json={},
        headers=invitee_headers,
    )
    if switch_resp.status_code == 200:
        # Use the new token
        invitee_headers = {
            "Authorization": f"Bearer {switch_resp.json()['access_token']}"
        }

    resp = requests.post(
        f"{BASE_URL}/organizations/invitations",
        json={"email": f"nobody-{RUN_ID}@example.com", "role": "member"},
        headers=invitee_headers,
    )
    assert resp.status_code == 403, (
        f"Expected 403 for non-admin, got {resp.status_code}: {resp.text}"
    )

    print(f"  Correctly rejected: {resp.json().get('detail', '')}")
    print("  ✓ Non-admin cannot create invitations")
    return True


def main():
    print("Invitation Flow Tests")
    print("=" * 60)

    # Register a fresh org-admin account (register creates user as org admin)
    register_user(ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_ORG_NAME)
    admin_headers = get_auth_headers(ADMIN_EMAIL, ADMIN_PASSWORD)
    print(f"✓ Registered and authenticated as org admin ({ADMIN_EMAIL})")

    results = []

    # Step 1: Create invitation
    invitation = test_create_invitation(admin_headers)
    results.append(("Create invitation", True))

    # Step 2: Verify it's in the list
    results.append(("Invitation in pending list",
                     test_invitation_appears_in_list(admin_headers, invitation["id"])))

    # Step 3: Duplicate rejected
    results.append(("Duplicate invitation rejected",
                     test_duplicate_invitation_rejected(admin_headers)))

    # Step 4-5: Register and accept
    results.append(("Accept invitation",
                     test_accept_invitation(invitation["token"])))

    # Step 6: Invitee is now a member
    results.append(("Invitee is member",
                     test_invitee_is_member(admin_headers)))

    # Step 7: Re-accept rejected
    results.append(("Re-accept rejected",
                     test_accept_again_rejected(invitation["token"])))

    # Step 8: Wrong user cannot accept
    results.append(("Wrong user blocked",
                     test_wrong_user_cannot_accept(admin_headers)))

    # Step 9: Cancel invitation
    results.append(("Cancel invitation",
                     test_cancel_invitation(admin_headers)))

    # Step 10: Invitation cannot overwrite password (security)
    results.append(("Password overwrite blocked",
                     test_invitation_cannot_overwrite_password(admin_headers)))

    # Step 11: Non-admin cannot invite
    results.append(("Non-admin cannot invite",
                     test_non_admin_cannot_invite()))

    # Summary
    print("\n" + "=" * 60)
    all_passed = True
    for name, passed in results:
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ All invitation flow tests passed!")
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
