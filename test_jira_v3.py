#!/usr/bin/env python3
"""
Test script to verify Jira API v3 upgrade.
"""

import requests
import json

def test_jira_v3_upgrade():
    """Test that Jira API has been upgraded to v3."""
    
    BASE_URL = "http://localhost:8000/api/v1"
    
    # Login
    print("1. Logging in...")
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "admin@example.com", "password": "admin123"}
    )
    
    if login_resp.status_code != 200:
        print(f"   ✗ Login failed: {login_resp.status_code}")
        return False
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✓ Login successful")
    
    # Create a test credential
    print("\n2. Creating test Jira credential...")
    test_cred = {
        "name": "V3 API Test",
        "server_url": "https://example.atlassian.net",
        "email": "test@example.com",
        "api_token": "test-token-v3"
    }
    
    create_resp = requests.post(
        f"{BASE_URL}/credentials/jira",
        json=test_cred,
        headers=headers
    )
    
    if create_resp.status_code != 200:
        print(f"   ✗ Failed to create credential: {create_resp.status_code}")
        return False
    
    cred_id = create_resp.json()["id"]
    print(f"   ✓ Created credential with ID: {cred_id}")
    
    # Test the credential endpoint
    print("\n3. Testing credential (will fail with fake URL, but check v3 endpoint)...")
    test_resp = requests.post(
        f"{BASE_URL}/credentials/{cred_id}/test",
        headers=headers
    )
    
    test_result = test_resp.json()
    test_url = test_result.get("test_url", "")
    
    # Check that we're using v3 API endpoints
    v3_indicators = [
        "/rest/api/3/" in test_url,
        "/search/jql" in test_url  # v3 uses /search/jql instead of /search
    ]
    
    print(f"   Test URL: {test_url}")
    
    if all(v3_indicators):
        print("   ✓ Using Jira API v3 endpoints!")
        print("     - Uses /rest/api/3/ path")
        print("     - Uses /search/jql endpoint (v3 specific)")
    else:
        print("   ✗ Not using v3 endpoints correctly")
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
    print("\nSummary:")
    print("- Backend correctly uses Jira API v3 endpoints")
    print("- Test endpoint uses /rest/api/3/search/jql")
    print("- JiraService has been upgraded to v3")
    print("\nTo test with real Jira instance:")
    print("1. Add credentials with actual Jira URL and API token")
    print("2. Click the test button to verify connection")
    print("3. The test will use v3 API to fetch recent issues")
    
    return True

if __name__ == "__main__":
    success = test_jira_v3_upgrade()
    exit(0 if success else 1)