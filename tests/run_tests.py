#!/usr/bin/env python3
"""
Main test runner for the Release Notes Agent application.
This script runs all available tests and provides a summary.
"""

import os
import sys
import subprocess
from pathlib import Path

import requests

# Add tests directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    API_BASE_URL, TEST_EMAIL, TEST_PASSWORD, ensure_test_account,
    HAS_JIRA_CREDS, HAS_AI_CREDS, HAS_HERETTO_CREDS,
)

class TestRunner:
    def __init__(self, no_cleanup: bool = False):
        self.tests_dir = Path(__file__).parent
        self.test_results = {}
        self.no_cleanup = no_cleanup
        self._auth_token = None

    def _get_auth_token(self) -> str:
        """Get an auth token for API calls."""
        if self._auth_token:
            return self._auth_token
        resp = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10,
        )
        resp.raise_for_status()
        self._auth_token = resp.json()["access_token"]
        return self._auth_token

    def _get_job_ids(self) -> set:
        """Fetch all current job IDs from the API."""
        token = self._get_auth_token()
        resp = requests.get(
            f"{API_BASE_URL}/jobs/?limit=1000",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return {job["id"] for job in resp.json()}

    def _cleanup_jobs(self, new_job_ids: set):
        """Delete jobs created during the test run."""
        if not new_job_ids:
            print("\nCleanup: No new jobs to delete.")
            return
        token = self._get_auth_token()
        deleted = 0
        errors = 0
        for job_id in new_job_ids:
            try:
                resp = requests.delete(
                    f"{API_BASE_URL}/jobs/{job_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    deleted += 1
                else:
                    errors += 1
                    print(f"  Warning: Failed to delete job {job_id} (HTTP {resp.status_code})")
            except Exception as e:
                errors += 1
                print(f"  Warning: Error deleting job {job_id}: {e}")
        print(f"\nCleanup: Deleted {deleted} test job(s).", end="")
        if errors:
            print(f" ({errors} failed)", end="")
        print()
        
    def run_python_test(self, test_file: Path, description: str) -> bool:
        """Run a Python test file and return success status."""
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"File: {test_file.relative_to(self.tests_dir)}")
        print('='*60)
        
        try:
            result = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            
            success = result.returncode == 0
            self.test_results[description] = "✓ PASSED" if success else "✗ FAILED"
            return success
            
        except subprocess.TimeoutExpired:
            print("✗ Test timed out after 60 seconds")
            self.test_results[description] = "✗ TIMEOUT"
            return False
        except Exception as e:
            print(f"✗ Error running test: {e}")
            self.test_results[description] = "✗ ERROR"
            return False
    
    def check_services(self) -> bool:
        """Check if required services are running."""
        print("\nChecking services...")
        
        # Check API
        try:
            resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
            if resp.status_code == 200:
                print("✓ API is running")
            else:
                print(f"✗ API returned status {resp.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print("✗ API is not running at", API_BASE_URL)
            print("  Please ensure Docker services are running:")
            print("  docker-compose up -d")
            return False
        except Exception as e:
            print(f"✗ Error checking API: {e}")
            return False
        
        return True
    
    def run_all_tests(self):
        """Run all tests in order."""
        print("\n" + "="*60)
        print("RELEASE NOTES AGENT - TEST SUITE")
        print("="*60)

        # Check services first
        if not self.check_services():
            print("\n⚠️  Services check failed. Please start the application first.")
            return

        # Ensure the default test account exists and is a superuser
        try:
            ensure_test_account()
            print("✓ Test account ready")
        except Exception as e:
            print(f"\n⚠️  Failed to set up test account: {e}")
            return

        # Snapshot existing job IDs before tests
        try:
            pre_test_job_ids = self._get_job_ids()
        except Exception as e:
            print(f"\nWarning: Could not snapshot jobs before tests: {e}")
            pre_test_job_ids = None

        # Define test order and descriptions
        tests = [
            # Unit Tests
            ("unit/test_dita_validation.py", "DITA Validation"),
            ("unit/test_settings.py", "Settings and Configuration"),
            ("unit/services/test_valid_models.py", "AI Model Names Validation"),

            # API Tests
            ("api/test_credentials.py", "Credentials CRUD Operations"),
            ("api/test_delete_artifacts.py", "Artifact Deletion"),
            ("api/test_superadmin_access.py", "Superadmin Access Control"),
            ("api/test_invitation_flow.py", "Invitation Flow"),
            ("api/test_multi_org_login.py", "Multi-Org Login Regression"),
            ("api/test_admin_visibility.py", "Admin Visibility Regression"),
            ("api/test_password_reset.py", "Password Reset Flow"),

            # Integration Tests
            ("integration/test_jira_v3.py", "JIRA API v3 Integration"),
            ("integration/test_jira_final.py", "JIRA Final Integration"),
            ("integration/test_heretto.py", "Heretto CCMS Integration"),
            ("integration/ai/test_configured_ai.py", "Configured AI Services"),
            ("integration/test_job_execution.py", "Job Execution"),
            ("integration/test_dita_validation_e2e.py", "DITA Validation End-to-End"),

            # Utilities Tests (optional, run if requested)
            # ("utilities/database/test_job_model_inspection.py", "Database Inspection"),
        ]

        passed = 0
        failed = 0

        for test_path, description in tests:
            test_file = self.tests_dir / test_path
            if test_file.exists():
                if self.run_python_test(test_file, description):
                    passed += 1
                else:
                    failed += 1
            else:
                print(f"\n⚠️  Test file not found: {test_path}")
                self.test_results[description] = "⚠️ NOT FOUND"
                failed += 1

        # Print summary
        self.print_summary(passed, failed)

        # Cleanup test jobs
        if pre_test_job_ids is not None:
            try:
                post_test_job_ids = self._get_job_ids()
                new_job_ids = post_test_job_ids - pre_test_job_ids
                if self.no_cleanup:
                    print(f"\nCleanup skipped (--no-cleanup): {len(new_job_ids)} test job(s) left in database.")
                else:
                    self._cleanup_jobs(new_job_ids)
            except Exception as e:
                print(f"\nWarning: Could not clean up test jobs: {e}")

        # Check for missing credentials and print setup guidance
        self._print_credential_hints()

        print("\nTip: To keep test data after a run: python run_tests.py --no-cleanup")
    
    def _print_credential_hints(self):
        """Check for missing .env credentials and print setup instructions."""
        missing_required = []
        missing_optional = []

        if not HAS_JIRA_CREDS:
            missing_required.append("Jira")
        if not HAS_AI_CREDS:
            missing_required.append("AI")
        if not HAS_HERETTO_CREDS:
            missing_optional.append("Heretto")

        if not missing_required and not missing_optional:
            return

        print("\n" + "-" * 60)
        print("CREDENTIAL SETUP (.env)")
        print("-" * 60)

        if missing_required:
            print(f"Missing required credentials: {', '.join(missing_required)}")
            print(f"Some integration tests were skipped. Add the following to your .env file:")
            print()
            if "Jira" in missing_required:
                print(f"  TEST_JIRA_URL=https://your-instance.atlassian.net")
                print(f"  TEST_JIRA_USERNAME=your-email@example.com")
                print(f"  TEST_JIRA_API_TOKEN=your-jira-api-token")
                print()
            if "AI" in missing_required:
                print(f"  # At least one of:")
                print(f"  TEST_CLAUDE_API_KEY=sk-ant-...")
                print(f"  TEST_OPENAI_API_KEY=sk-...")
                print(f"  GOOGLE_AI_API_KEY=...")
                print()

        if missing_optional:
            if missing_required:
                print()
            print(f"Optional credentials not configured: {', '.join(missing_optional)}")
            print(f"  Heretto CCMS integration tests will be skipped.")
            print(f"  To enable them, add to .env:")
            print(f"    TEST_HERETTO_SERVER=https://your-heretto-instance.com")
            print(f"    TEST_HERETTO_LOGIN_USER=your-username")
            print(f"    TEST_HERETTO_LOGIN_TOKEN=your-token")

    def print_summary(self, passed: int, failed: int):
        """Print test results summary."""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        for test, result in self.test_results.items():
            print(f"{result:12} {test}")
        
        print("\n" + "-"*60)
        total = passed + failed
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        if failed == 0:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️  {failed} test(s) failed")
        print("="*60)

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Release Notes Agent tests')
    parser.add_argument('--test', help='Run specific test file', default=None)
    parser.add_argument('--list', action='store_true', help='List available tests')
    parser.add_argument('--no-cleanup', action='store_true',
                        help='Skip cleanup of test jobs after run')

    args = parser.parse_args()

    runner = TestRunner(no_cleanup=args.no_cleanup)
    
    if args.list:
        print("\nAvailable test files:")
        print("-" * 40)
        for root, dirs, files in os.walk(runner.tests_dir):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(root, file), runner.tests_dir)
                    print(f"  {rel_path}")
        print("\nUI Test Guides (manual testing):")
        print("-" * 40)
        for root, dirs, files in os.walk(runner.tests_dir / 'ui'):
            for file in files:
                if file.endswith('.md'):
                    rel_path = os.path.relpath(os.path.join(root, file), runner.tests_dir)
                    print(f"  {rel_path}")
    elif args.test:
        # Run specific test
        test_file = runner.tests_dir / args.test
        if test_file.exists():
            runner.run_python_test(test_file, args.test)
        else:
            print(f"Test file not found: {args.test}")
            sys.exit(1)
    else:
        # Run all tests
        runner.run_all_tests()

if __name__ == "__main__":
    main()