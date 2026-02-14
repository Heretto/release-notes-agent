#!/usr/bin/env python3
"""
Main test runner for the Release Notes Agent application.
This script runs all available tests and provides a summary.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add tests directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

class TestRunner:
    def __init__(self):
        self.tests_dir = Path(__file__).parent
        self.test_results = {}
        
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
        import requests
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
        
        # Define test order and descriptions
        tests = [
            # Unit Tests
            ("unit/test_dita_validation.py", "DITA Validation"),
            ("unit/test_settings.py", "Settings and Configuration"),
            ("unit/services/test_valid_models.py", "AI Model Names Validation"),
            
            # API Tests
            ("api/test_credentials.py", "Credentials CRUD Operations"),
            ("api/test_delete_artifacts.py", "Artifact Deletion"),
            
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
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
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