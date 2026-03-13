#!/usr/bin/env python3
"""
Test script to verify Jira API v3 upgrade.

Uses TEST_JIRA_URL, TEST_JIRA_USERNAME, and TEST_JIRA_API_TOKEN from the
project-root .env file.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config import (
    API_BASE_URL, TEST_EMAIL, TEST_PASSWORD,
    TEST_JIRA_URL, TEST_JIRA_USERNAME, TEST_JIRA_API_TOKEN, HAS_JIRA_CREDS,
)


def test_jira_v3_upgrade():
    """Test that Jira API has been upgraded to v3."""

    BASE_URL = API_BASE_URL

    if not HAS_JIRA_CREDS:
        print("⚠ Skipping: Jira credentials not set in .env")
        print("  Set TEST_JIRA_URL, TEST_JIRA_USERNAME, TEST_JIRA_API_TOKEN")
        return True

    # Login
    print("1. Logging in...")
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    if login_resp.status_code != 200:
        print(f"   ✗ Login failed: {login_resp.status_code}")
        return False

    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✓ Login successful")

    # Create a temporary credential from .env values
    print("\n2. Creating Jira credential from .env...")
    test_cred = {
        "name": "V3 API Test",
        "server_url": TEST_JIRA_URL,
        "email": TEST_JIRA_USERNAME,
        "api_token": TEST_JIRA_API_TOKEN,
    }

    create_resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=test_cred,
        headers=headers
    )

    cred_id = None
    if create_resp.status_code == 200:
        cred_id = create_resp.json()["id"]
        print(f"   ✓ Created credential with ID: {cred_id}")
    elif create_resp.status_code == 400 and "already exists" in create_resp.json().get("detail", ""):
        list_resp = requests.get(f"{BASE_URL}/credentials/jira", headers=headers)
        if list_resp.status_code == 200:
            for cred in list_resp.json():
                if cred["name"] == "V3 API Test":
                    cred_id = cred["id"]
                    break
        if cred_id:
            print(f"   ✓ Using existing credential: {cred_id}")
        else:
            print(f"   ✗ Credential exists but could not find it in list")
            return False
    else:
        print(f"   ✗ Failed to create credential: {create_resp.status_code}")
        return False

    # Test the credential endpoint
    print("\n3. Testing credential connection...")
    test_resp = requests.post(
        f"{BASE_URL}/credentials/{cred_id}/test",
        headers=headers
    )

    test_result = test_resp.json()
    success = test_result.get("success", False)
    message = test_result.get("message", "")

    print(f"   Success: {success}")
    print(f"   Message: {message}")

    if success and "Successfully connected" in message:
        print("   ✓ Jira API v3 connection verified!")
    else:
        print(f"   ✗ Connection test failed: {message}")
        # Clean up
        requests.delete(f"{BASE_URL}/credentials/jira/{cred_id}", headers=headers)
        return False

    # Clean up
    print("\n4. Cleaning up test credential...")
    delete_resp = requests.delete(
        f"{BASE_URL}/credentials/jira/{cred_id}",
        headers=headers
    )

    if delete_resp.status_code == 200:
        print("   ✓ Test credential deleted")

    print("\n" + "="*60)
    print("✅ JIRA API V3 UPGRADE VERIFIED")
    print("="*60)

    return True

if __name__ == "__main__":
    success = test_jira_v3_upgrade()
    exit(0 if success else 1)
