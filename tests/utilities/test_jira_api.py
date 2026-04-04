#!/usr/bin/env python3
"""Test Jira credential through API"""

import requests
import json

# First login to get token
login_url = "http://localhost:8000/api/v1/auth/login"
login_data = {
    "email": "admin@ex.com",
    "password": "Admin123!"
}

print("🔑 Logging in...")
login_response = requests.post(login_url, json=login_data)
if login_response.status_code != 200:
    print(f"❌ Login failed: {login_response.text}")
    exit(1)

token = login_response.json()["access_token"]
print("✅ Login successful")

# Get the credential ID for testing
headers = {
    "Authorization": f"Bearer {token}"
}

# List Jira credentials
list_url = "http://localhost:8000/api/v1/credentials/jira"
print("\n📋 Fetching Jira credentials...")
list_response = requests.get(list_url, headers=headers)

if list_response.status_code != 200:
    print(f"❌ Failed to list credentials: {list_response.text}")
    exit(1)

credentials = list_response.json()
print(f"Found {len(credentials)} Jira credential(s)")

if not credentials:
    print("❌ No Jira credentials available")
    exit(1)

# Test the most recent credential
test_cred = credentials[-1]  # Get the last one (PJB Test Key)
print(f"\n🧪 Testing credential: {test_cred['name']}")
print(f"   Server: {test_cred['server_url']}")

# Test the credential
test_url = f"http://localhost:8000/api/v1/credentials/{test_cred['id']}/test"
print(f"\n🔌 Testing connection...")
test_response = requests.post(test_url, headers=headers)

if test_response.status_code != 200:
    print(f"❌ Test request failed: {test_response.text}")
else:
    result = test_response.json()
    if result.get("success"):
        print(f"✅ {result['message']}")
        if 'response_body' in result and 'total' in result['response_body']:
            print(f"   Found {result['response_body']['total']} accessible issues")
    else:
        print(f"❌ {result.get('message', 'Test failed')}")
        if 'error' in result:
            print(f"   Error: {result['error']}")