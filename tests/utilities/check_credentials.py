#!/usr/bin/env python3
"""
Check and display current test credentials status
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

def check_credentials():
    """Check if test credentials work."""
    print("Checking Test Credentials")
    print("="*40)
    print(f"API URL: {API_BASE_URL}")
    print(f"Email: {TEST_EMAIL}")
    print(f"Password: {TEST_PASSWORD}")
    print("-"*40)
    
    # Try to login
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=5
        )
        
        if response.status_code == 200:
            print("✓ Login successful!")
            token = response.json().get("access_token", "")
            print(f"  Token (first 20 chars): {token[:20]}...")
            return True
        else:
            print(f"✗ Login failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            
            # Try alternate password
            alt_passwords = ["admin123", "admin", "password"]
            for alt_pass in alt_passwords:
                print(f"\nTrying alternate password: {alt_pass}")
                alt_response = requests.post(
                    f"{API_BASE_URL}/auth/login",
                    json={"email": TEST_EMAIL, "password": alt_pass},
                    timeout=5
                )
                if alt_response.status_code == 200:
                    print(f"✓ Login successful with password: {alt_pass}")
                    print(f"\nUpdate tests/config.py with:")
                    print(f'TEST_PASSWORD = "{alt_pass}"')
                    return True
            
            print("\n✗ No working password found")
            print("\nTo reset admin password, run:")
            print("  python tests/utilities/reset_admin_password.py")
            return False
            
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API")
        print("\nMake sure services are running:")
        print("  docker-compose up -d")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    check_credentials()