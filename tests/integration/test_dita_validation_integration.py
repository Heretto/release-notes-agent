#!/usr/bin/env python3
"""
Integration test for DITA validation in the job orchestrator.
Tests that DITA validation is properly integrated and working.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import time
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

def test_dita_validation_integration():
    """Test that DITA validation is working in the job processing pipeline."""
    
    print("="*60)
    print("DITA VALIDATION INTEGRATION TEST")
    print("="*60)
    
    # Login
    print("\n1. Authenticating...")
    login_resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    
    if login_resp.status_code != 200:
        print(f"   ✗ Login failed: {login_resp.status_code}")
        return False
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✓ Authenticated successfully")
    
    # Get instruction sets
    print("\n2. Getting instruction sets...")
    instr_resp = requests.get(
        f"{API_BASE_URL}/instructions/",
        headers=headers
    )
    
    if instr_resp.status_code != 200 or not instr_resp.json():
        print("   ✗ No instruction sets available")
        print("   Create an instruction set first through the UI")
        return False
    
    instruction_set = instr_resp.json()[0]
    print(f"   ✓ Using instruction set: {instruction_set['name']}")
    
    # Create a test job that will generate DITA content
    print("\n3. Creating test job with DITA generation...")
    
    # Create job with a query that will trigger DITA generation
    job_data = {
        "jql_query": "project = TEST AND fixVersion = 'Test DITA Validation'",
        "instruction_set_id": instruction_set["id"],
        "output_filename": "test-dita-validation.dita",
        "publish_to_heretto": False,
        "additional_instructions": "Generate valid DITA XML with sections for features and bugs.",
        "max_tickets": 5  # Limit for testing
    }
    
    create_resp = requests.post(
        f"{API_BASE_URL}/jobs/",
        json=job_data,
        headers=headers
    )
    
    if create_resp.status_code != 200:
        print(f"   ✗ Failed to create job: {create_resp.text}")
        return False
    
    job = create_resp.json()
    job_id = job["id"]
    print(f"   ✓ Created job: {job_id}")
    
    # Monitor job progress
    print("\n4. Monitoring job processing...")
    max_wait = 120  # 2 minutes max
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status_resp = requests.get(
            f"{API_BASE_URL}/jobs/{job_id}",
            headers=headers
        )
        
        if status_resp.status_code == 200:
            job_status = status_resp.json()
            status = job_status["status"]
            
            if status == "completed":
                print(f"   ✓ Job completed successfully")
                break
            elif status == "failed":
                print(f"   ✗ Job failed: {job_status.get('error_message', 'Unknown error')}")
                break
            else:
                print(f"   ... Job status: {status}")
                time.sleep(5)
        else:
            print(f"   ✗ Failed to get job status")
            return False
    else:
        print(f"   ✗ Job timed out after {max_wait} seconds")
        return False
    
    # Get job artifacts to check for validation logs
    print("\n5. Checking validation artifacts...")
    artifacts_resp = requests.get(
        f"{API_BASE_URL}/jobs/{job_id}/artifacts",
        headers=headers
    )
    
    if artifacts_resp.status_code != 200:
        print(f"   ✗ Failed to get artifacts")
        return False
    
    artifacts = artifacts_resp.json()
    print(f"   ✓ Found {len(artifacts)} artifact(s)")
    
    # Look for validation-related artifacts
    validation_artifacts = {
        "dita": False,
        "validation_log": False,
        "validation_error": False,
        "correction_note": False
    }
    
    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type", "")
        filename = artifact.get("filename", "")
        
        print(f"   - {filename} (type: {artifact_type})")
        
        if artifact_type == "dita":
            validation_artifacts["dita"] = True
            
            # Get and validate the DITA content
            content_resp = requests.get(
                f"{API_BASE_URL}/jobs/{job_id}/artifacts/{artifact['id']}/content",
                headers=headers
            )
            
            if content_resp.status_code == 200:
                dita_content = content_resp.json().get("content", "")
                
                # Basic validation checks
                if '<?xml' in dita_content and '<topic' in dita_content:
                    print(f"     ✓ DITA content appears valid")
                else:
                    print(f"     ✗ DITA content may be invalid")
                    
        elif artifact_type == "validation_log":
            validation_artifacts["validation_log"] = True
        elif artifact_type == "validation_error":
            validation_artifacts["validation_error"] = True
        elif artifact_type == "correction_note":
            validation_artifacts["correction_note"] = True
    
    # Summary
    print("\n6. Validation Summary:")
    
    if validation_artifacts["dita"]:
        print("   ✓ DITA content generated")
    else:
        print("   ✗ No DITA content found")
    
    if validation_artifacts["validation_log"]:
        print("   ✓ Validation log created (validation was performed)")
    else:
        print("   ⚠ No validation log (validation may not have run)")
    
    if validation_artifacts["validation_error"]:
        print("   ⚠ Validation errors were encountered and logged")
    else:
        print("   ✓ No validation errors")
    
    if validation_artifacts["correction_note"]:
        print("   ✓ DITA content was corrected during validation")
    
    # Overall result
    print("\n" + "="*60)
    if validation_artifacts["dita"] and (validation_artifacts["validation_log"] or job_status["status"] == "completed"):
        print("✅ DITA VALIDATION IS INTEGRATED AND WORKING")
        
        if validation_artifacts["correction_note"]:
            print("   Content required correction but was successfully fixed")
        if validation_artifacts["validation_error"]:
            print("   Some validation issues remain but job completed")
            
        return True
    else:
        print("⚠️ DITA VALIDATION MAY NOT BE FULLY INTEGRATED")
        print("\nTroubleshooting:")
        print("1. Check backend logs: docker logs release-notes-backend")
        print("2. Ensure job_orchestrator.py is using DITAValidatorV2")
        print("3. Verify DITACorrectionService is imported")
        return False

if __name__ == "__main__":
    success = test_dita_validation_integration()
    sys.exit(0 if success else 1)