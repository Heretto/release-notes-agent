#!/usr/bin/env python3
"""Test to simulate connection errors"""

import httpx
import asyncio
import pytest

@pytest.mark.asyncio
async def test_various_urls():
    """Test different URL scenarios that might cause connection errors."""
    
    test_cases = [
        ("https://jorsek.atlassian.net", "Valid Jira URL"),
        ("https://invalid-domain-12345.atlassian.net", "Invalid domain"),
        ("http://jorsek.atlassian.net", "HTTP instead of HTTPS"),
        ("https://jorsek.atlassian.net:443", "With explicit port"),
        ("jorsek.atlassian.net", "Missing protocol"),
        ("https://", "Invalid URL format"),
    ]
    
    for url, description in test_cases:
        print(f"\n📍 Testing: {description}")
        print(f"   URL: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{url}/rest/api/3/myself")
                print(f"   ✅ Connected - Status: {response.status_code}")
        except httpx.ConnectError as e:
            error_msg = str(e)
            if "All connection attempts failed" in error_msg:
                print(f"   ❌ All connection attempts failed")
                print(f"      Details: {error_msg[:100]}...")
            else:
                print(f"   ❌ Connection error: {error_msg[:100]}...")
        except httpx.UnsupportedProtocol as e:
            print(f"   ❌ Protocol error: {e}")
        except httpx.InvalidURL as e:
            print(f"   ❌ Invalid URL: {e}")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Connection Error Simulation")
    print("=" * 60)
    asyncio.run(test_various_urls())