#!/usr/bin/env python3
"""Tests for credentials CRUD operations via the HTTP API."""

import sys
import os
import requests
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

BASE_URL = API_BASE_URL


def get_auth_headers():
    """Login and return authorization headers."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def cleanup_credential(headers, cred_id):
    """Delete a credential by ID (best-effort)."""
    requests.delete(f"{BASE_URL}/credentials/jira/{cred_id}", headers=headers)


def test_create_jira_credential(headers):
    """Test creating a new Jira credential."""
    print("\nTest: Create Jira credential")
    print("-" * 40)

    unique = uuid.uuid4().hex[:8]
    credential_data = {
        "name": f"Test Jira {unique}",
        "server_url": "https://test.atlassian.net",
        "email": "jira@example.com",
        "api_token": "test-token-123"
    }

    resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=credential_data,
        headers=headers
    )

    assert resp.status_code == 200, f"Create failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["name"] == credential_data["name"]
    assert data["type"] == "jira"
    assert "id" in data
    print(f"  ✓ Created credential: {data['id']}")

    # Cleanup
    cleanup_credential(headers, data["id"])
    return True


def test_list_jira_credentials(headers):
    """Test listing Jira credentials."""
    print("\nTest: List Jira credentials")
    print("-" * 40)

    unique = uuid.uuid4().hex[:8]
    credential_data = {
        "name": f"List Test {unique}",
        "server_url": "https://list-test.atlassian.net",
        "email": "list@example.com",
        "api_token": "list-token-123"
    }

    create_resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=credential_data,
        headers=headers
    )
    assert create_resp.status_code == 200, f"Create failed: {create_resp.status_code}"
    created_id = create_resp.json()["id"]

    # List credentials
    resp = requests.get(f"{BASE_URL}/credentials/jira", headers=headers)
    assert resp.status_code == 200, f"List failed: {resp.status_code}"

    credentials = resp.json()
    assert isinstance(credentials, list)
    assert len(credentials) > 0

    found = any(cred["id"] == created_id for cred in credentials)
    assert found, "Created credential not found in list"
    print(f"  ✓ Listed credentials, found created ID in list")

    # Cleanup
    cleanup_credential(headers, created_id)
    return True


def test_update_jira_credential(headers):
    """Test updating a Jira credential."""
    print("\nTest: Update Jira credential")
    print("-" * 40)

    unique = uuid.uuid4().hex[:8]
    credential_data = {
        "name": f"Update Test {unique}",
        "server_url": "https://update-test.atlassian.net",
        "email": "update@example.com",
        "api_token": "update-token-123"
    }

    create_resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=credential_data,
        headers=headers
    )
    assert create_resp.status_code == 200, f"Create failed: {create_resp.status_code}"
    created_id = create_resp.json()["id"]

    # Update
    update_data = {
        "name": f"Updated Jira {unique}",
        "server_url": "https://updated.atlassian.net"
    }

    resp = requests.put(
        f"{BASE_URL}/credentials/jira/{created_id}",
        json=update_data,
        headers=headers
    )

    assert resp.status_code == 200, f"Update failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["name"] == update_data["name"]
    print(f"  ✓ Updated credential name to: {data['name']}")

    # Cleanup
    cleanup_credential(headers, created_id)
    return True


def test_delete_jira_credential(headers):
    """Test deleting a Jira credential."""
    print("\nTest: Delete Jira credential")
    print("-" * 40)

    unique = uuid.uuid4().hex[:8]
    credential_data = {
        "name": f"Delete Test {unique}",
        "server_url": "https://delete-test.atlassian.net",
        "email": "delete@example.com",
        "api_token": "delete-token-123"
    }

    create_resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=credential_data,
        headers=headers
    )
    assert create_resp.status_code == 200, f"Create failed: {create_resp.status_code}"
    created_id = create_resp.json()["id"]

    # Delete
    resp = requests.delete(
        f"{BASE_URL}/credentials/jira/{created_id}",
        headers=headers
    )
    assert resp.status_code == 200, f"Delete failed: {resp.status_code}"

    # Verify deleted
    list_resp = requests.get(f"{BASE_URL}/credentials/jira", headers=headers)
    credentials = list_resp.json()
    found = any(cred["id"] == created_id for cred in credentials)
    assert not found, "Credential still exists after deletion"
    print(f"  ✓ Deleted credential and verified removal")

    return True


def test_duplicate_name_error(headers):
    """Test that creating a credential with duplicate name fails."""
    print("\nTest: Duplicate name error")
    print("-" * 40)

    unique = uuid.uuid4().hex[:8]
    credential_data = {
        "name": f"Duplicate Test {unique}",
        "server_url": "https://dup.atlassian.net",
        "email": "dup@example.com",
        "api_token": "dup-token-123"
    }

    # Create first
    resp1 = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=credential_data,
        headers=headers
    )
    assert resp1.status_code == 200, f"First create failed: {resp1.status_code}"
    created_id = resp1.json()["id"]

    # Try duplicate
    resp2 = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=credential_data,
        headers=headers
    )
    assert resp2.status_code == 400, f"Expected 400, got {resp2.status_code}"
    assert "already exists" in resp2.json()["detail"]
    print(f"  ✓ Duplicate correctly rejected with 400")

    # Cleanup
    cleanup_credential(headers, created_id)
    return True


def test_missing_fields_error(headers):
    """Test that missing required fields returns an error."""
    print("\nTest: Missing fields error")
    print("-" * 40)

    incomplete_data = {
        "name": "Incomplete Test",
        "server_url": "https://incomplete.atlassian.net"
        # Missing email and api_token
    }

    resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=incomplete_data,
        headers=headers
    )

    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert "Missing required" in resp.json()["detail"]
    print(f"  ✓ Missing fields correctly rejected with 400")

    return True


def test_unauthorized_access():
    """Test that requests without authentication are rejected."""
    print("\nTest: Unauthorized access")
    print("-" * 40)

    resp = requests.get(f"{BASE_URL}/credentials/jira")
    assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
    print(f"  ✓ Unauthorized request rejected with {resp.status_code}")

    return True


def test_ai_credential_test_endpoint(headers):
    """Test the AI credential test endpoint (regression: must not return 500)."""
    print("\nTest: AI credential test endpoint")
    print("-" * 40)

    unique = uuid.uuid4().hex[:8]

    # Create an AI credential
    ai_cred = {
        "provider": "openai",
        "name": f"AI Test {unique}",
        "api_key": "sk-test-fake-key-for-regression",
        "model": "gpt-4"
    }

    create_resp = requests.post(
        f"{BASE_URL}/credentials/ai",
        json=ai_cred,
        headers=headers
    )
    assert create_resp.status_code == 200, f"Create AI cred failed: {create_resp.status_code} {create_resp.text}"
    cred_id = create_resp.json()["id"]

    # Test the credential - must NOT return 500
    test_resp = requests.post(
        f"{BASE_URL}/credentials/{cred_id}/test",
        headers=headers
    )
    assert test_resp.status_code != 500, f"Test endpoint returned 500 Internal Server Error"
    assert test_resp.status_code == 200, f"Test endpoint returned {test_resp.status_code}: {test_resp.text}"

    data = test_resp.json()
    assert "success" in data, "Response missing 'success' field"
    assert "status_code" in data, "Response missing 'status_code' field"
    assert "message" in data, "Response missing 'message' field"
    # With a fake key, the AI provider should reject auth (not crash)
    print(f"  ✓ Test endpoint returned valid response (success={data['success']}, status={data['status_code']})")

    # Cleanup
    requests.delete(f"{BASE_URL}/credentials/{cred_id}", headers=headers)
    print(f"  ✓ Cleaned up test credential")

    return True


def test_ai_credential_test_corrupt_decrypt(headers):
    """Regression: test endpoint must not 500 when credential data can't be decrypted."""
    print("\nTest: AI credential test with corrupt encrypted data")
    print("-" * 40)

    # Find any AI credential with stale/corrupt encrypted data
    # (credentials created under a different encryption key)
    list_resp = requests.get(f"{BASE_URL}/credentials/ai", headers=headers)
    assert list_resp.status_code == 200

    stale_creds = []
    for cred in list_resp.json():
        test_resp = requests.post(
            f"{BASE_URL}/credentials/{cred['id']}/test",
            headers=headers
        )
        if test_resp.status_code == 400 and "decrypt" in test_resp.json().get("detail", "").lower():
            stale_creds.append(cred["id"])

    if stale_creds:
        print(f"  ✓ Found {len(stale_creds)} credential(s) with stale encryption — all returned 400 (not 500)")
    else:
        print(f"  ✓ No stale credentials found (all decrypted successfully)")

    # Regardless, verify no 500s were returned for any AI credential
    for cred in list_resp.json():
        test_resp = requests.post(
            f"{BASE_URL}/credentials/{cred['id']}/test",
            headers=headers
        )
        assert test_resp.status_code != 500, (
            f"Credential {cred['id']} returned 500 Internal Server Error"
        )

    print(f"  ✓ No 500 errors for any AI credential test")
    return True


if __name__ == "__main__":
    print("Credentials CRUD Operations Tests")
    print("=" * 60)

    headers = get_auth_headers()
    print("✓ Authenticated")

    results = []
    results.append(("Create", test_create_jira_credential(headers)))
    results.append(("List", test_list_jira_credentials(headers)))
    results.append(("Update", test_update_jira_credential(headers)))
    results.append(("Delete", test_delete_jira_credential(headers)))
    results.append(("Duplicate", test_duplicate_name_error(headers)))
    results.append(("Missing Fields", test_missing_fields_error(headers)))
    results.append(("Unauthorized", test_unauthorized_access()))
    results.append(("AI Test Endpoint", test_ai_credential_test_endpoint(headers)))
    results.append(("AI Corrupt Decrypt", test_ai_credential_test_corrupt_decrypt(headers)))

    print("\n" + "=" * 60)
    all_passed = True
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ All credentials tests passed!")
    else:
        print("\n✗ Some credentials tests failed")
        sys.exit(1)
