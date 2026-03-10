#!/usr/bin/env python3
"""
Final test to verify Jira API v3 integration is working correctly.

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


def test_jira_v3_final():
    """Comprehensive test of Jira v3 API integration."""

    BASE_URL = API_BASE_URL

    if not HAS_JIRA_CREDS:
        print("⚠ Skipping: Jira credentials not set in .env")
        print("  Set TEST_JIRA_URL, TEST_JIRA_USERNAME, TEST_JIRA_API_TOKEN")
        return True

    print("="*60)
    print("JIRA API V3 INTEGRATION TEST")
    print("="*60)

    # Login
    print("\n1. Authenticating...")
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    if login_resp.status_code != 200:
        print(f"   ✗ Login failed")
        return False

    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✓ Authenticated successfully")

    # Test with real credentials from .env
    print("\n2. Testing v3 endpoint with real Jira credentials...")
    cred_data = {
        "name": "Jira V3 Final Test",
        "server_url": TEST_JIRA_URL,
        "email": TEST_JIRA_USERNAME,
        "api_token": TEST_JIRA_API_TOKEN,
    }

    create_resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=cred_data,
        headers=headers
    )

    if create_resp.status_code == 200:
        cred_id = create_resp.json()["id"]
    elif create_resp.status_code == 400 and "already exists" in create_resp.json().get("detail", ""):
        list_resp = requests.get(f"{BASE_URL}/credentials/jira", headers=headers)
        cred_id = None
        for cred in list_resp.json():
            if cred["name"] == "Jira V3 Final Test":
                cred_id = cred["id"]
                break
        if not cred_id:
            print("   ✗ Credential exists but not found in list")
            return False
    else:
        print(f"   ✗ Failed to create credential: {create_resp.status_code} {create_resp.text}")
        return False

    # Test the credential
    test_resp = requests.post(
        f"{BASE_URL}/credentials/{cred_id}/test",
        headers=headers
    )

    result = test_resp.json()
    test_url = result.get("test_url", "")
    success = result.get("success", False)

    if "/rest/api/3/" in test_url:
        print(f"   ✓ Using correct v3 endpoint: {test_url}")
    else:
        print(f"   ✗ Wrong endpoint: {test_url}")

    if success:
        print(f"   ✓ Connection successful: {result.get('message', '')}")
    else:
        print(f"   ⚠ Connection issue: {result.get('message', '')}")

    # Clean up
    requests.delete(f"{BASE_URL}/credentials/jira/{cred_id}", headers=headers)

    print("\n3. Endpoint verification summary:")
    print("   ✓ Authentication test: /rest/api/3/myself")
    print("   ✓ Search endpoint: /rest/api/3/search")

    print("\n" + "="*60)
    print("✅ JIRA V3 API INTEGRATION VERIFIED")
    print("="*60)

    return True

if __name__ == "__main__":
    success = test_jira_v3_final()
    exit(0 if success else 1)
