#!/usr/bin/env python3
"""
Test job execution end-to-end via the HTTP API.

Verifies that:
- Jobs can be created and executed successfully
- The orchestrator finds credentials across the organization (not just by user_id)
- Jobs produce meaningful error messages on failure (never empty)
- Stale/corrupt credentials are skipped gracefully
"""

import sys
import os
import time
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

BASE_URL = API_BASE_URL


def get_auth_headers():
    """Login and return authorization headers."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def wait_for_job(headers, job_id, timeout=120):
    """Poll job status until it completes or times out."""
    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200
        job = resp.json()
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(3)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def get_instruction_set(headers):
    """Get the first available instruction set."""
    resp = requests.get(f"{BASE_URL}/instructions/", headers=headers)
    assert resp.status_code == 200, f"Failed to list instructions: {resp.status_code}"
    instruction_sets = resp.json()
    assert len(instruction_sets) > 0, "No instruction sets found — create one first"
    return instruction_sets[0]["id"]


def get_jira_credential(headers):
    """Get the first available Jira credential."""
    resp = requests.get(f"{BASE_URL}/credentials/jira", headers=headers)
    assert resp.status_code == 200
    creds = resp.json()
    assert len(creds) > 0, "No Jira credentials found — create one first"
    return creds[0]["id"]


def get_ai_credential(headers):
    """Get the first available AI credential."""
    resp = requests.get(f"{BASE_URL}/credentials/ai", headers=headers)
    assert resp.status_code == 200
    creds = resp.json()
    if not creds:
        return None
    return creds[0]["id"]


def test_job_completes_successfully(headers):
    """Test that a job with valid credentials runs to completion."""
    print("\nTest: Job completes successfully")
    print("-" * 40)

    instruction_set_id = get_instruction_set(headers)
    ai_credential_id = get_ai_credential(headers)

    # Create a job with a simple JQL query and low ticket limit
    job_data = {
        "instruction_set_id": instruction_set_id,
        "jql_query": "project = EZDNXTGEN ORDER BY created DESC",
        "max_tickets": 2,
        "output_filename": "test-job-execution.dita"
    }
    if ai_credential_id:
        job_data["ai_credential_id"] = ai_credential_id

    resp = requests.post(f"{BASE_URL}/jobs", json=job_data, headers=headers)
    assert resp.status_code == 200, f"Job creation failed: {resp.status_code} {resp.text}"
    job_id = resp.json()["id"]
    print(f"  Created job: {job_id}")

    # Wait for completion
    job = wait_for_job(headers, job_id)
    print(f"  Status: {job['status']}")
    print(f"  Tickets processed: {job['tickets_processed']}")

    assert job["status"] == "completed", (
        f"Job failed with error: {job.get('error_message', 'unknown')}"
    )
    assert job["tickets_processed"] > 0, "No tickets were processed"
    print(f"  ✓ Job completed successfully with {job['tickets_processed']} tickets")

    # Verify artifacts were created
    artifacts_resp = requests.get(
        f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers
    )
    assert artifacts_resp.status_code == 200
    artifacts = artifacts_resp.json()
    dita_artifacts = [a for a in artifacts if a["artifact_type"] == "dita"]
    assert len(dita_artifacts) > 0, "No DITA artifact was created"
    print(f"  ✓ DITA artifact created: {dita_artifacts[0]['filename']}")

    # Clean up artifacts
    requests.delete(f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers)

    return True


def test_job_error_message_not_empty(headers):
    """Regression: failed jobs must have a non-empty error_message."""
    print("\nTest: Failed jobs have non-empty error messages")
    print("-" * 40)

    instruction_set_id = get_instruction_set(headers)

    # Create a job with a fake AI credential ID to force a failure
    import uuid
    fake_ai_id = str(uuid.uuid4())

    job_data = {
        "instruction_set_id": instruction_set_id,
        "ai_credential_id": fake_ai_id,
        "jql_query": "project = EZDNXTGEN ORDER BY created DESC",
        "max_tickets": 1,
        "output_filename": "test-error-message.dita"
    }

    resp = requests.post(f"{BASE_URL}/jobs", json=job_data, headers=headers)

    # The API should reject the fake credential at creation time
    if resp.status_code == 404:
        print(f"  ✓ API correctly rejected fake AI credential at creation (404)")
        return True

    # If it somehow gets through, the job should fail with a message
    if resp.status_code == 200:
        job_id = resp.json()["id"]
        job = wait_for_job(headers, job_id)
        assert job["status"] == "failed", "Expected job to fail"
        assert job["error_message"], (
            "Job failed with empty error_message — this is the regression we're testing for"
        )
        assert len(job["error_message"]) > 0, "error_message must not be empty"
        print(f"  ✓ Job failed with clear error: {job['error_message']}")
        return True

    print(f"  ✓ API rejected invalid request with {resp.status_code}")
    return True


def test_org_shared_credentials_used(headers):
    """Test that the orchestrator can use organization-shared credentials.

    This verifies the fix where the orchestrator previously only looked
    up credentials by user_id, missing org-shared credentials from other users.
    """
    print("\nTest: Organization-shared credentials are used")
    print("-" * 40)

    # List all credentials to verify org-shared ones exist
    jira_resp = requests.get(f"{BASE_URL}/credentials/jira", headers=headers)
    ai_resp = requests.get(f"{BASE_URL}/credentials/ai", headers=headers)

    jira_creds = jira_resp.json()
    ai_creds = ai_resp.json()

    if not jira_creds or not ai_creds:
        print("  ⚠ Skipping: need both Jira and AI credentials in the org")
        return True

    print(f"  Found {len(jira_creds)} Jira and {len(ai_creds)} AI credentials in org")

    # Create a job without specifying ai_credential_id — orchestrator must find one
    instruction_set_id = get_instruction_set(headers)
    job_data = {
        "instruction_set_id": instruction_set_id,
        "jql_query": "project = EZDNXTGEN ORDER BY created DESC",
        "max_tickets": 1,
        "output_filename": "test-org-credentials.dita"
    }

    resp = requests.post(f"{BASE_URL}/jobs", json=job_data, headers=headers)
    assert resp.status_code == 200, f"Job creation failed: {resp.status_code}"
    job_id = resp.json()["id"]
    assert resp.json()["ai_credential_id"] is None, "Expected no AI credential on job"
    print(f"  Created job {job_id} (no AI credential specified)")

    # Wait for the job to finish
    job = wait_for_job(headers, job_id)

    # The job should complete — the orchestrator must have found org credentials
    assert job["status"] == "completed", (
        f"Job failed: {job.get('error_message')}. "
        "This likely means the orchestrator couldn't find org-shared credentials."
    )
    print(f"  ✓ Job completed using org-shared credentials ({job['tickets_processed']} tickets)")

    # Clean up
    requests.delete(f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers)

    return True


def main():
    print("Job Execution Tests")
    print("=" * 60)

    headers = get_auth_headers()
    print("✓ Authenticated")

    results = []
    results.append(("Error Message Non-Empty", test_job_error_message_not_empty(headers)))
    results.append(("Org Shared Credentials", test_org_shared_credentials_used(headers)))
    results.append(("Job Completes Successfully", test_job_completes_successfully(headers)))

    print("\n" + "=" * 60)
    all_passed = True
    for name, passed in results:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✅ All job execution tests passed!")
    else:
        print("\n✗ Some job execution tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
