#!/usr/bin/env python3
"""Test login endpoint"""

import requests
import json

# Test credentials
email = "admin@ex.com"
password = "Admin123!"

# Make login request
url = "http://localhost:8000/api/v1/auth/login"
payload = {
    "email": email,
    "password": password
}

print(f"Testing login with email: {email}")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(url, json=payload)
    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Login successful!")
        print(f"Access Token: {data.get('access_token', '')[:50]}...")
        print(f"Token Type: {data.get('token_type', '')}")
    else:
        print(f"❌ Login failed!")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")