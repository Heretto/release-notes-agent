#!/usr/bin/env python3
"""
Test script to verify multi-tenant data isolation in the release notes agent.
This script tests that organizations can only access their own data.
"""

import sys
import os
import argparse
import requests
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime
import uuid

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class DataIsolationTester:
    def __init__(self, api_url: str = "http://localhost:8000/api/v1", database_url: str = None):
        self.api_url = api_url
        self.database_url = database_url or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db/release_notes")
        self.engine = create_engine(self.database_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Test data storage
        self.test_orgs: List[Dict] = []
        self.test_users: List[Dict] = []
        self.test_data: Dict[str, Dict] = {}
        
    def cleanup(self):
        """Clean up test data from the database."""
        print("\n🧹 Cleaning up test data...")
        
        try:
            # Rollback any pending transactions
            self.session.rollback()
        except:
            pass
        
        # Delete test users and organizations
        for user_data in self.test_users:
            user = self.session.query(User).filter(User.email == user_data['email']).first()
            if user:
                # Delete memberships first
                self.session.execute(
                    text("DELETE FROM organization_members WHERE user_id = :user_id"),
                    {"user_id": user.id}
                )
                # Delete user
                self.session.delete(user)
        
        for org_data in self.test_orgs:
            org = self.session.query(Organization).filter(Organization.name == org_data['name']).first()
            if org:
                # Delete all related data
                self.session.execute(
                    text("DELETE FROM credentials WHERE organization_id = :org_id"),
                    {"org_id": org.id}
                )
                self.session.execute(
                    text("DELETE FROM instruction_sets WHERE organization_id = :org_id"),
                    {"org_id": org.id}
                )
                self.session.execute(
                    text("DELETE FROM jobs WHERE organization_id = :org_id"),
                    {"org_id": org.id}
                )
                self.session.execute(
                    text("DELETE FROM organization_invitations WHERE organization_id = :org_id"),
                    {"org_id": org.id}
                )
                self.session.execute(
                    text("DELETE FROM organization_members WHERE organization_id = :org_id"),
                    {"org_id": org.id}
                )
                # Delete organization
                self.session.delete(org)
        
        self.session.commit()
        print("✅ Test data cleaned up")
    
    def setup_test_organizations(self) -> None:
        """Create test organizations and users."""
        print("\n📦 Setting up test organizations...")
        
        # Create two test organizations
        org_configs = [
            {"name": f"TestOrg_A_{uuid.uuid4().hex[:8]}", "email": "test_a@example.com", "password": "TestPass123!"},
            {"name": f"TestOrg_B_{uuid.uuid4().hex[:8]}", "email": "test_b@example.com", "password": "TestPass456!"}
        ]
        
        for config in org_configs:
            # Check if user already exists
            existing_user = self.session.query(User).filter(
                User.email == config['email']
            ).first()
            
            if existing_user:
                print(f"⚠️  User {config['email']} already exists, cleaning up...")
                # Delete existing user's memberships and organizations
                self.session.execute(
                    text("DELETE FROM organization_members WHERE user_id = :user_id"),
                    {"user_id": existing_user.id}
                )
                self.session.delete(existing_user)
                self.session.commit()
            
            # Check if org exists
            existing_org = self.session.query(Organization).filter(
                Organization.name == config['name']
            ).first()
            
            if not existing_org:
                # Create organization with slug
                slug = config['name'].lower().replace(' ', '-').replace('_', '-')
                org = Organization(name=config['name'], slug=slug)
                self.session.add(org)
                self.session.flush()
                
                # Create admin user
                user = User(
                    email=config['email'],
                    password_hash=get_password_hash(config['password']),
                    is_active=True,
                    is_superuser=False
                )
                self.session.add(user)
                self.session.flush()
                
                # Add user as admin to organization
                member = OrganizationMember(
                    organization_id=org.id,
                    user_id=user.id,
                    role=OrganizationRole.ADMIN
                )
                self.session.add(member)
                
                self.session.commit()
                
                self.test_orgs.append({"name": config['name'], "id": str(org.id)})
                self.test_users.append({
                    "email": config['email'],
                    "password": config['password'],
                    "org_name": config['name'],
                    "org_id": str(org.id)
                })
                
                print(f"✅ Created organization: {config['name']} with admin: {config['email']}")
            else:
                print(f"⚠️  Organization {config['name']} already exists, skipping...")
    
    def get_auth_token(self, email: str, password: str) -> str:
        """Get authentication token for a user."""
        response = requests.post(
            f"{self.api_url}/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to authenticate {email}: {response.text}")
            return None
            
        return response.json()["access_token"]
    
    def create_test_data(self, token: str, org_name: str) -> Dict[str, Any]:
        """Create test data for an organization."""
        headers = {"Authorization": f"Bearer {token}"}
        created_data = {}
        
        # Create a credential
        cred_data = {
            "name": f"{org_name}_TestCredential",
            "type": "jira",  # Use valid type
            "credentials": {"api_key": f"test_key_{org_name}", "email": "test@example.com", "server": "https://test.atlassian.net"}
        }
        response = requests.post(
            f"{self.api_url}/credentials",
            json=cred_data,
            headers=headers
        )
        if response.status_code == 200:
            created_data['credential'] = response.json()
            print(f"  ✅ Created credential: {cred_data['name']}")
        else:
            print(f"  ❌ Failed to create credential: {response.text}")
        
        # Create an instruction (with proper format for this app)
        inst_data = {
            "name": f"{org_name}_TestInstruction",
            "jql_query": f"project = TEST_{org_name}",
            "system_prompt": f"Test system prompt for {org_name}",
            "is_active": True
        }
        response = requests.post(
            f"{self.api_url}/instructions",
            json=inst_data,
            headers=headers
        )
        if response.status_code == 200:
            created_data['instruction'] = response.json()
            print(f"  ✅ Created instruction: {inst_data['name']}")
        else:
            print(f"  ❌ Failed to create instruction: {response.text}")
        
        # Create a job (if credentials and instructions exist)
        if 'credential' in created_data and 'instruction' in created_data:
            job_data = {
                "name": f"{org_name}_TestJob",
                "jql_query": f"project = TEST_{org_name}",
                "credential_id": created_data['credential']['id'],
                "instruction_set_id": created_data['instruction']['id'],
                "output_filename": f"test_output_{org_name}.md"
            }
            response = requests.post(
                f"{self.api_url}/jobs",
                json=job_data,
                headers=headers
            )
            if response.status_code == 200:
                created_data['job'] = response.json()
                print(f"  ✅ Created job: {job_data['name']}")
            else:
                print(f"  ❌ Failed to create job: {response.text}")
        
        return created_data
    
    def test_data_isolation(self) -> Tuple[int, int]:
        """Test that organizations cannot access each other's data."""
        print("\n🔒 Testing data isolation...")
        passed_tests = 0
        failed_tests = 0
        
        # Get tokens for both organizations
        org_a = self.test_users[0]
        org_b = self.test_users[1]
        
        token_a = self.get_auth_token(org_a['email'], org_a['password'])
        token_b = self.get_auth_token(org_b['email'], org_b['password'])
        
        if not token_a or not token_b:
            print("❌ Failed to authenticate test users")
            return 0, 1
        
        # Create test data for each organization
        print("\n📝 Creating test data for Organization A...")
        data_a = self.create_test_data(token_a, org_a['org_name'])
        
        print("\n📝 Creating test data for Organization B...")
        data_b = self.create_test_data(token_b, org_b['org_name'])
        
        # Test isolation for each resource type
        print("\n🧪 Running isolation tests...")
        
        # Test 1: Organization A should not see Organization B's credentials
        headers_a = {"Authorization": f"Bearer {token_a}"}
        response = requests.get(f"{self.api_url}/credentials", headers=headers_a)
        if response.status_code == 200:
            creds = response.json()
            org_b_creds = [c for c in creds if org_b['org_name'] in c.get('name', '')]
            if len(org_b_creds) == 0:
                print("  ✅ Test 1: Org A cannot see Org B's credentials")
                passed_tests += 1
            else:
                print(f"  ❌ Test 1: Org A can see {len(org_b_creds)} of Org B's credentials")
                failed_tests += 1
        else:
            print(f"  ❌ Test 1: Failed to fetch credentials: {response.text}")
            failed_tests += 1
        
        # Test 2: Organization B should not see Organization A's instructions
        headers_b = {"Authorization": f"Bearer {token_b}"}
        response = requests.get(f"{self.api_url}/instructions", headers=headers_b)
        if response.status_code == 200:
            instructions = response.json()
            org_a_inst = [i for i in instructions if org_a['org_name'] in i.get('name', '')]
            if len(org_a_inst) == 0:
                print("  ✅ Test 2: Org B cannot see Org A's instructions")
                passed_tests += 1
            else:
                print(f"  ❌ Test 2: Org B can see {len(org_a_inst)} of Org A's instructions")
                failed_tests += 1
        else:
            print(f"  ❌ Test 2: Failed to fetch instructions: {response.text}")
            failed_tests += 1
        
        # Test 3: Organization A should not see Organization B's jobs
        response = requests.get(f"{self.api_url}/jobs", headers=headers_a)
        if response.status_code == 200:
            jobs = response.json()
            org_b_jobs = [j for j in jobs if org_b['org_name'] in j.get('name', '')]
            if len(org_b_jobs) == 0:
                print("  ✅ Test 3: Org A cannot see Org B's jobs")
                passed_tests += 1
            else:
                print(f"  ❌ Test 3: Org A can see {len(org_b_jobs)} of Org B's jobs")
                failed_tests += 1
        else:
            print(f"  ❌ Test 3: Failed to fetch jobs: {response.text}")
            failed_tests += 1
        
        # Test 4: Organization A should not be able to access Org B's specific credential
        if 'credential' in data_b:
            response = requests.get(
                f"{self.api_url}/credentials/{data_b['credential']['id']}",
                headers=headers_a
            )
            if response.status_code in [403, 404]:
                print("  ✅ Test 4: Org A cannot access Org B's specific credential")
                passed_tests += 1
            else:
                print(f"  ❌ Test 4: Org A can access Org B's credential (status: {response.status_code})")
                failed_tests += 1
        else:
            print("  ⚠️  Test 4: Skipped (no credential created for Org B)")
        
        # Test 5: Organization B should not be able to modify Org A's instruction
        if 'instruction' in data_a:
            update_data = {"name": "Hacked_Instruction", "content": "Hacked content"}
            response = requests.put(
                f"{self.api_url}/instructions/{data_a['instruction']['id']}",
                json=update_data,
                headers=headers_b
            )
            if response.status_code in [403, 404]:
                print("  ✅ Test 5: Org B cannot modify Org A's instruction")
                passed_tests += 1
            else:
                print(f"  ❌ Test 5: Org B can modify Org A's instruction (status: {response.status_code})")
                failed_tests += 1
        else:
            print("  ⚠️  Test 5: Skipped (no instruction created for Org A)")
        
        # Test 6: Organization A should not be able to delete Org B's job
        if 'job' in data_b:
            response = requests.delete(
                f"{self.api_url}/jobs/{data_b['job']['id']}",
                headers=headers_a
            )
            if response.status_code in [403, 404]:
                print("  ✅ Test 6: Org A cannot delete Org B's job")
                passed_tests += 1
            else:
                print(f"  ❌ Test 6: Org A can delete Org B's job (status: {response.status_code})")
                failed_tests += 1
        else:
            print("  ⚠️  Test 6: Skipped (no job created for Org B)")
        
        # Test 7: Check organization member isolation
        response = requests.get(f"{self.api_url}/organizations/current/members", headers=headers_a)
        if response.status_code == 200:
            members = response.json()
            org_b_members = [m for m in members if m.get('email') == org_b['email']]
            if len(org_b_members) == 0:
                print("  ✅ Test 7: Org A cannot see Org B's members")
                passed_tests += 1
            else:
                print(f"  ❌ Test 7: Org A can see Org B's members")
                failed_tests += 1
        else:
            print(f"  ❌ Test 7: Failed to fetch members: {response.text}")
            failed_tests += 1
        
        # Test 8: Each org should only see their own data counts
        for user, token, expected_org in [(org_a, token_a, 'A'), (org_b, token_b, 'B')]:
            headers = {"Authorization": f"Bearer {token}"}
            
            # Check credentials count
            response = requests.get(f"{self.api_url}/credentials", headers=headers)
            if response.status_code == 200:
                creds = response.json()
                expected_count = 1  # Each org created 1 credential
                if len(creds) == expected_count:
                    print(f"  ✅ Test 8.{expected_org}: Org {expected_org} sees correct credential count")
                    passed_tests += 1
                else:
                    print(f"  ❌ Test 8.{expected_org}: Org {expected_org} sees {len(creds)} credentials (expected {expected_count})")
                    failed_tests += 1
            else:
                failed_tests += 1
        
        return passed_tests, failed_tests
    
    def run_tests(self) -> bool:
        """Run all data isolation tests."""
        try:
            print("\n" + "="*60)
            print("🚀 MULTI-TENANT DATA ISOLATION TEST SUITE")
            print("="*60)
            
            # Setup test data
            self.setup_test_organizations()
            
            # Run isolation tests
            passed, failed = self.test_data_isolation()
            
            # Print summary
            print("\n" + "="*60)
            print("📊 TEST RESULTS SUMMARY")
            print("="*60)
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            total = passed + failed
            if total > 0:
                success_rate = (passed / total) * 100
                print(f"📈 Success Rate: {success_rate:.1f}%")
                
                if failed == 0:
                    print("\n🎉 ALL TESTS PASSED! Data isolation is working correctly.")
                    return True
                else:
                    print("\n⚠️  SOME TESTS FAILED! Review the data isolation implementation.")
                    return False
            else:
                print("\n⚠️  No tests were run.")
                return False
                
        except Exception as e:
            print(f"\n❌ Test execution failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Always cleanup
            self.cleanup()
            self.session.close()


def main():
    parser = argparse.ArgumentParser(description='Test multi-tenant data isolation')
    parser.add_argument(
        '--api-url',
        default='http://localhost:8000/api/v1',
        help='API base URL (default: http://localhost:8000/api/v1)'
    )
    parser.add_argument(
        '--database-url',
        default=None,
        help='Database URL (default: from DATABASE_URL env var)'
    )
    
    args = parser.parse_args()
    
    # Import models here for main execution
    global User, Organization, OrganizationMember, OrganizationRole, get_password_hash
    from app.models.database import User
    from app.models.organization import Organization, OrganizationMember, OrganizationRole
    from app.core.security import get_password_hash
    
    tester = DataIsolationTester(api_url=args.api_url, database_url=args.database_url)
    success = tester.run_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()