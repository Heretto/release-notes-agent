#!/usr/bin/env python3
"""
Test script for Jira credentials CRUD operations.
This script will:
1. Login to get authentication token
2. Create a new Jira credential
3. Verify it was created
4. Update the credential
5. Delete the credential
6. Verify it was deleted
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from typing import Optional, Dict, Any
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

BASE_URL = API_BASE_URL
TEST_USER = TEST_EMAIL
TEST_PASSWORD = TEST_PASSWORD

class CredentialsTest:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.created_credential_id = None
    
    def login(self) -> bool:
        """Login and get access token."""
        print("1. Logging in...")
        response = self.session.post(
            f"{BASE_URL}/auth/login",
            json={"email": TEST_USER, "password": TEST_PASSWORD}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
            print("   ✓ Login successful")
            return True
        else:
            print(f"   ✗ Login failed: {response.status_code} - {response.text}")
            return False
    
    def create_jira_credential(self) -> bool:
        """Create a new Jira credential."""
        print("\n2. Creating Jira credential...")
        credential_data = {
            "name": "Test Jira Instance",
            "server_url": "https://test.atlassian.net",
            "email": "test@example.com",
            "api_token": "test-api-token-123"
        }
        
        response = self.session.post(
            f"{BASE_URL}/credentials/jira",
            json=credential_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.created_credential_id = data["id"]
            print(f"   ✓ Credential created with ID: {self.created_credential_id}")
            print(f"     Name: {data['name']}")
            print(f"     Type: {data['type']}")
            return True
        else:
            print(f"   ✗ Failed to create credential: {response.status_code}")
            print(f"     Error: {response.text}")
            return False
    
    def list_jira_credentials(self) -> bool:
        """List all Jira credentials and verify our test credential exists."""
        print("\n3. Listing Jira credentials...")
        response = self.session.get(f"{BASE_URL}/credentials/jira")
        
        if response.status_code == 200:
            credentials = response.json()
            print(f"   ✓ Found {len(credentials)} Jira credential(s)")
            
            # Check if our created credential is in the list
            found = False
            for cred in credentials:
                if cred["id"] == self.created_credential_id:
                    found = True
                    print(f"   ✓ Test credential found in list:")
                    print(f"     - ID: {cred['id']}")
                    print(f"     - Name: {cred['name']}")
                    print(f"     - Type: {cred['type']}")
                    break
            
            if not found:
                print(f"   ✗ Test credential {self.created_credential_id} not found in list")
                return False
            
            return True
        else:
            print(f"   ✗ Failed to list credentials: {response.status_code}")
            print(f"     Error: {response.text}")
            return False
    
    def update_jira_credential(self) -> bool:
        """Update the test Jira credential."""
        print("\n4. Updating Jira credential...")
        
        if not self.created_credential_id:
            print("   ✗ No credential ID available for update")
            return False
        
        update_data = {
            "name": "Updated Test Jira",
            "server_url": "https://updated-test.atlassian.net"
        }
        
        response = self.session.put(
            f"{BASE_URL}/credentials/jira/{self.created_credential_id}",
            json=update_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Credential updated successfully")
            print(f"     New name: {data['name']}")
            return True
        else:
            print(f"   ✗ Failed to update credential: {response.status_code}")
            print(f"     Error: {response.text}")
            return False
    
    def delete_jira_credential(self) -> bool:
        """Delete the test Jira credential."""
        print("\n5. Deleting Jira credential...")
        
        if not self.created_credential_id:
            print("   ✗ No credential ID available for deletion")
            return False
        
        response = self.session.delete(
            f"{BASE_URL}/credentials/jira/{self.created_credential_id}"
        )
        
        if response.status_code == 200:
            print(f"   ✓ Credential {self.created_credential_id} deleted successfully")
            return True
        else:
            print(f"   ✗ Failed to delete credential: {response.status_code}")
            print(f"     Error: {response.text}")
            return False
    
    def verify_deletion(self) -> bool:
        """Verify the credential was actually deleted."""
        print("\n6. Verifying deletion...")
        response = self.session.get(f"{BASE_URL}/credentials/jira")
        
        if response.status_code == 200:
            credentials = response.json()
            
            # Check if our deleted credential is still in the list
            found = False
            for cred in credentials:
                if cred["id"] == self.created_credential_id:
                    found = True
                    break
            
            if found:
                print(f"   ✗ Credential {self.created_credential_id} still exists!")
                return False
            else:
                print(f"   ✓ Credential successfully removed from database")
                return True
        else:
            print(f"   ✗ Failed to list credentials: {response.status_code}")
            return False
    
    def cleanup(self):
        """Clean up any remaining test credentials."""
        if self.created_credential_id:
            try:
                self.session.delete(
                    f"{BASE_URL}/credentials/jira/{self.created_credential_id}"
                )
            except:
                pass
    
    def run_all_tests(self) -> bool:
        """Run all test cases."""
        print("=" * 60)
        print("JIRA CREDENTIALS CRUD TEST SUITE")
        print("=" * 60)
        
        all_passed = True
        
        # Run tests in sequence
        tests = [
            self.login,
            self.create_jira_credential,
            self.list_jira_credentials,
            self.update_jira_credential,
            self.delete_jira_credential,
            self.verify_deletion
        ]
        
        for test in tests:
            if not test():
                all_passed = False
                print("\n⚠️  Test failed, stopping test suite")
                break
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL TESTS PASSED")
        else:
            print("❌ SOME TESTS FAILED")
            # Clean up if needed
            self.cleanup()
        print("=" * 60)
        
        return all_passed

def main():
    """Main test runner."""
    tester = CredentialsTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()