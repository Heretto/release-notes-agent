#!/usr/bin/env python3
"""Test network connectivity to Jira"""

import httpx
import asyncio
import socket
import sys
import pytest

@pytest.mark.asyncio
async def test_connection():
    """Test connection to Jira server."""
    jira_host = "jorsek.atlassian.net"
    jira_url = f"https://{jira_host}"
    
    print(f"🌐 Testing connection to {jira_host}")
    
    # Test DNS resolution
    print("\n1. Testing DNS resolution...")
    try:
        ip = socket.gethostbyname(jira_host)
        print(f"   ✅ DNS resolved to: {ip}")
    except socket.gaierror as e:
        print(f"   ❌ DNS resolution failed: {e}")
        return
    
    # Test HTTPS connection
    print("\n2. Testing HTTPS connection...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jira_url, follow_redirects=True)
            print(f"   ✅ HTTPS connection successful")
            print(f"   Status code: {response.status_code}")
            print(f"   Response headers: {dict(list(response.headers.items())[:3])}")
    except httpx.ConnectError as e:
        print(f"   ❌ Connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")
    except httpx.TimeoutException as e:
        print(f"   ❌ Connection timed out: {e}")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        print(f"   Error type: {type(e).__name__}")
    
    # Test Jira API endpoint
    print("\n3. Testing Jira API endpoint...")
    api_url = f"https://{jira_host}/rest/api/3/serverInfo"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(api_url)
            print(f"   ✅ API endpoint reachable")
            print(f"   Status code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Server version: {data.get('version', 'Unknown')}")
    except httpx.ConnectError as e:
        print(f"   ❌ API connection failed: {e}")
        # More detailed error info
        import traceback
        print("\n   Detailed error:")
        traceback.print_exc()
    except Exception as e:
        print(f"   ❌ API test failed: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Network Connectivity Test")
    print("=" * 60)
    asyncio.run(test_connection())