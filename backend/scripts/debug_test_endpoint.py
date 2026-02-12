#!/usr/bin/env python3
"""Debug the test endpoint to see what's happening"""

import requests
import json
import time

# Login first
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
headers = {"Authorization": f"Bearer {token}"}
print("✅ Logged in successfully")

# Get Jira credentials
list_url = "http://localhost:8000/api/v1/credentials/jira"
print("\n📋 Getting Jira credentials...")
list_response = requests.get(list_url, headers=headers)

if list_response.status_code != 200:
    print(f"❌ Failed to list credentials: {list_response.text}")
    exit(1)

credentials = list_response.json()
print(f"Found {len(credentials)} credential(s)")

if not credentials:
    print("❌ No Jira credentials found")
    exit(1)

# Test each credential
for cred in credentials:
    print(f"\n🧪 Testing: {cred['name']}")
    print(f"   ID: {cred['id']}")
    print(f"   Server: {cred['server_url']}")
    
    test_url = f"http://localhost:8000/api/v1/credentials/{cred['id']}/test"
    
    print(f"   Making request to: {test_url}")
    start_time = time.time()
    
    try:
        # Make the test request with a longer timeout
        test_response = requests.post(test_url, headers=headers, timeout=60)
        elapsed = time.time() - start_time
        
        print(f"   Response time: {elapsed:.2f}s")
        print(f"   Status code: {test_response.status_code}")
        
        if test_response.status_code == 200:
            result = test_response.json()
            if result.get("success"):
                print(f"   ✅ {result.get('message', 'Success')}")
            else:
                print(f"   ❌ {result.get('message', 'Failed')}")
                if 'error' in result:
                    print(f"   Error: {result['error']}")
                if 'error_details' in result:
                    print(f"   Details: {result['error_details']}")
        else:
            print(f"   ❌ HTTP {test_response.status_code}: {test_response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"   ❌ Request timed out after 60 seconds")
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Connection error: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {type(e).__name__}: {e}")