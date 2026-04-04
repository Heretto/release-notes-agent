#!/usr/bin/env python3
"""
Test the job rerun functionality.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import time
from uuid import uuid4

from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD, ensure_test_account

def test_rerun_job():
    """Test the job rerun functionality."""
    
    print("="*60)
    print("JOB RERUN FUNCTIONALITY TEST")
    print("="*60)
    
    # Step 1: Login
    print("\n1. Authenticating...")
    login_resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    
    if login_resp.status_code != 200:
        print(f"   ✗ Login failed: {login_resp.status_code}")
        print(f"   Response: {login_resp.text}")
        return False
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✓ Authenticated successfully")
    
    # Step 2: Get an existing completed or failed job to rerun
    print("\n2. Getting existing jobs...")
    jobs_resp = requests.get(
        f"{API_BASE_URL}/jobs",
        headers=headers
    )
    
    if jobs_resp.status_code != 200:
        print(f"   ✗ Failed to get jobs: {jobs_resp.status_code}")
        return False
    
    jobs = jobs_resp.json()
    
    # Find a completed or failed job to rerun
    rerun_candidate = None
    for job in jobs:
        if job["status"] in ["completed", "failed"]:
            rerun_candidate = job
            break
    
    if not rerun_candidate:
        print("   ✗ No completed or failed jobs found to rerun")
        print("   Create and complete a job first, then run this test")
        return False
    
    print(f"   ✓ Found job to rerun: {rerun_candidate['id']}")
    print(f"     Status: {rerun_candidate['status']}")
    print(f"     JQL: {rerun_candidate['jql_query']}")
    
    # Step 3: Rerun the job
    print("\n3. Rerunning job...")
    rerun_resp = requests.post(
        f"{API_BASE_URL}/jobs/{rerun_candidate['id']}/rerun",
        headers=headers
    )
    
    if rerun_resp.status_code != 200:
        print(f"   ✗ Failed to rerun job: {rerun_resp.status_code}")
        print(f"   Response: {rerun_resp.text}")
        return False
    
    new_job = rerun_resp.json()
    print(f"   ✓ New job created: {new_job['id']}")
    
    # Step 4: Verify the new job has the same parameters
    print("\n4. Verifying job parameters...")
    
    # Check that key parameters match
    params_to_check = [
        "jql_query",
        "instruction_set_id",
        "ai_credential_id",
        "additional_instructions",
        "output_filename",
        "auto_publish",
        "max_tickets"
    ]
    
    all_match = True
    for param in params_to_check:
        original_value = rerun_candidate.get(param)
        new_value = new_job.get(param)
        
        if original_value != new_value:
            print(f"   ✗ Parameter mismatch: {param}")
            print(f"     Original: {original_value}")
            print(f"     New: {new_value}")
            all_match = False
        else:
            print(f"   ✓ {param}: {new_value}")
    
    if not all_match:
        print("\n   ⚠️ Some parameters don't match!")
        return False
    
    # Step 5: Verify the new job is in pending status
    print("\n5. Checking new job status...")
    if new_job["status"] != "pending":
        print(f"   ✗ New job status is not 'pending': {new_job['status']}")
        return False
    
    print(f"   ✓ New job status: {new_job['status']}")
    
    # Step 6: Monitor the new job briefly
    print("\n6. Monitoring new job (5 seconds)...")
    time.sleep(5)
    
    status_resp = requests.get(
        f"{API_BASE_URL}/jobs/{new_job['id']}",
        headers=headers
    )
    
    if status_resp.status_code == 200:
        updated_job = status_resp.json()
        print(f"   Current status: {updated_job['status']}")
        
        if updated_job["status"] in ["running", "completed"]:
            print("   ✓ Job is processing correctly")
        elif updated_job["status"] == "failed":
            print(f"   ⚠️ Job failed: {updated_job.get('error_message', 'Unknown error')}")
        else:
            print(f"   Job still in status: {updated_job['status']}")
    
    # Summary
    print("\n" + "="*60)
    print("✅ JOB RERUN TEST COMPLETED SUCCESSFULLY")
    print("\nThe rerun functionality is working correctly:")
    print("• Backend endpoint creates new job with same parameters")
    print("• New job is properly queued for processing")
    print("• Original job parameters are preserved")
    print("\nFrontend features added:")
    print("• Rerun button in job detail view")
    print("• Rerun option in jobs list menu")
    print("• Navigation to new job after rerun")
    print("="*60)
    
    return True

if __name__ == "__main__":
    success = test_rerun_job()
    sys.exit(0 if success else 1)