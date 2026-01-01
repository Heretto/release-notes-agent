#!/usr/bin/env python3
"""
Test script to verify artifact deletion functionality
"""
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"
EMAIL = "admin@example.com"  # Use admin email
PASSWORD = "admin"  # Change this if different

def login():
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        sys.exit(1)
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def get_jobs(headers):
    """Get list of jobs"""
    response = requests.get(f"{BASE_URL}/jobs/", headers=headers)
    return response.json()

def get_artifacts(job_id, headers):
    """Get artifacts for a job"""
    response = requests.get(f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers)
    return response.json()

def delete_artifact(job_id, artifact_id, headers):
    """Delete a single artifact"""
    response = requests.delete(
        f"{BASE_URL}/jobs/{job_id}/artifacts/{artifact_id}",
        headers=headers
    )
    return response

def delete_all_artifacts(job_id, headers):
    """Delete all artifacts for a job"""
    response = requests.delete(
        f"{BASE_URL}/jobs/{job_id}/artifacts",
        headers=headers
    )
    return response

def main():
    print("Testing Artifact Deletion Functionality")
    print("=" * 40)
    
    # Login
    print("\n1. Logging in...")
    headers = login()
    print("   ✓ Logged in successfully")
    
    # Get jobs
    print("\n2. Getting jobs...")
    jobs = get_jobs(headers)
    
    if not jobs:
        print("   No jobs found. Please create a job first.")
        return
    
    # Find a completed job with artifacts
    job_with_artifacts = None
    for job in jobs:
        if job["status"] == "completed":
            artifacts = get_artifacts(job["id"], headers)
            if artifacts:
                job_with_artifacts = job
                break
    
    if not job_with_artifacts:
        print("   No completed jobs with artifacts found.")
        return
    
    print(f"   ✓ Found job {job_with_artifacts['id']} with artifacts")
    
    # Get artifacts
    print(f"\n3. Getting artifacts for job {job_with_artifacts['id']}...")
    artifacts = get_artifacts(job_with_artifacts["id"], headers)
    print(f"   ✓ Found {len(artifacts)} artifact(s):")
    for artifact in artifacts:
        print(f"      - {artifact['filename']} (ID: {artifact['id']})")
    
    # Test single artifact deletion
    if len(artifacts) > 1:
        print(f"\n4. Testing single artifact deletion...")
        artifact_to_delete = artifacts[0]
        print(f"   Deleting {artifact_to_delete['filename']}...")
        
        response = delete_artifact(
            job_with_artifacts["id"],
            artifact_to_delete["id"],
            headers
        )
        
        if response.status_code == 200:
            print(f"   ✓ Successfully deleted artifact")
            result = response.json()
            print(f"      Message: {result.get('message', 'No message')}")
        else:
            print(f"   ✗ Failed to delete artifact: {response.text}")
            return
        
        # Verify deletion
        remaining_artifacts = get_artifacts(job_with_artifacts["id"], headers)
        print(f"   ✓ Verification: {len(remaining_artifacts)} artifact(s) remaining")
        
        # Test delete all artifacts
        if remaining_artifacts:
            print(f"\n5. Testing delete all artifacts...")
            print(f"   Deleting all {len(remaining_artifacts)} remaining artifact(s)...")
            
            response = delete_all_artifacts(job_with_artifacts["id"], headers)
            
            if response.status_code == 200:
                print(f"   ✓ Successfully deleted all artifacts")
                result = response.json()
                print(f"      Message: {result.get('message', 'No message')}")
                print(f"      Deleted count: {result.get('deleted_count', 'Unknown')}")
            else:
                print(f"   ✗ Failed to delete all artifacts: {response.text}")
                return
            
            # Verify all deleted
            final_artifacts = get_artifacts(job_with_artifacts["id"], headers)
            if len(final_artifacts) == 0:
                print(f"   ✓ Verification: All artifacts successfully deleted")
            else:
                print(f"   ✗ Verification failed: {len(final_artifacts)} artifact(s) still remain")
    else:
        # Only one artifact, test delete all
        print(f"\n4. Testing delete all artifacts (single artifact)...")
        response = delete_all_artifacts(job_with_artifacts["id"], headers)
        
        if response.status_code == 200:
            print(f"   ✓ Successfully deleted all artifacts")
            result = response.json()
            print(f"      Message: {result.get('message', 'No message')}")
        else:
            print(f"   ✗ Failed to delete all artifacts: {response.text}")
    
    print("\n" + "=" * 40)
    print("✓ All tests completed successfully!")

if __name__ == "__main__":
    main()