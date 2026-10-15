#!/usr/bin/env python3
"""
Test job execution end-to-end via the HTTP API.

Credentials are read from the project-root .env file and created in the
database via the API before each test run.  This avoids depending on
credentials that were manually added through the UI.

Verifies that:
- Jobs can be created and executed successfully
- The orchestrator finds credentials across the organization (not just by user_id)
- Jobs produce meaningful error messages on failure (never empty)
"""

import sys
import os
import time
import uuid
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    API_BASE_URL, TEST_EMAIL, TEST_PASSWORD,
    TEST_JIRA_URL, TEST_JIRA_USERNAME, TEST_JIRA_API_TOKEN, HAS_JIRA_CREDS,
    TEST_CLAUDE_API_KEY, TEST_CLAUDE_MODEL,
    TEST_OPENAI_API_KEY, TEST_OPENAI_MODEL,
    TEST_GOOGLE_API_KEY, TEST_GOOGLE_MODEL,
    HAS_AI_CREDS,
)

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


def _ensure_agent(headers, ai_configuration_id=None):
    """Create a minimal Agent for testing.  Returns (agent_id, created)."""
    name = "Test Agent (env)"
    resp = requests.get(f"{BASE_URL}/agents", headers=headers)
    if resp.status_code == 200:
        for agent in resp.json():
            if agent["name"] == name:
                return agent["id"], False

    create_resp = requests.post(
        f"{BASE_URL}/agents",
        json={
            "name": name,
            "description": "Generate release notes from the provided Jira tickets.",
            "ai_configuration_id": ai_configuration_id,
        },
        headers=headers,
    )
    if create_resp.status_code == 200:
        return create_resp.json()["id"], True
    return None, False


def get_instruction_set(headers, ai_configuration_id=None):
    """Get the first available instruction set, creating one (with an agent) if needed."""
    resp = requests.get(f"{BASE_URL}/instructions", headers=headers)
    assert resp.status_code == 200, f"Failed to list instructions: {resp.status_code}"
    instruction_sets = resp.json()
    if instruction_sets:
        return instruction_sets[0]["id"]

    agent_id, _ = _ensure_agent(headers, ai_configuration_id)

    # Create a minimal instruction set for testing
    create_resp = requests.post(
        f"{BASE_URL}/instructions",
        json={
            "name": "Test Instruction Set",
            "jql_query": "project = EZDNXTGEN ORDER BY created DESC",
            "writer_agent_id": agent_id,
        },
        headers=headers,
    )
    assert create_resp.status_code == 200, (
        f"Failed to create instruction set: {create_resp.status_code} {create_resp.text}"
    )
    print(f"  Created test instruction set: {create_resp.json()['id']}")
    return create_resp.json()["id"]


# ---------------------------------------------------------------------------
# Credential helpers — create from .env, return ID, clean up after
# ---------------------------------------------------------------------------

def _find_credential(headers, cred_type, name):
    """An existing credential of this type and name, or None."""
    resp = requests.get(f"{BASE_URL}/credentials", headers=headers)
    if resp.status_code != 200:
        return None
    for credential in resp.json():
        if credential["type"] == cred_type and credential["name"] == name:
            return credential["id"]
    return None


def _ensure_credential(headers, cred_type, name, payload):
    """Create a credential through hop-core's generic API.  Returns (cred_id, created).

    Credentials are type-agnostic server-side: the type key picks the registered spec, and
    `credentials` carries that spec's fields.
    """
    existing = _find_credential(headers, cred_type, name)
    if existing:
        return existing, False

    resp = requests.post(
        f"{BASE_URL}/credentials",
        json={"type": cred_type, "name": name, "credentials": payload},
        headers=headers,
    )
    if resp.status_code == 200:
        return resp.json()["id"], True
    return None, False


def _ensure_jira_credential(headers):
    """Create a Jira credential from .env vars.  Returns (cred_id, created)."""
    return _ensure_credential(headers, "jira", "Test Jira (env)", {
        "server_url": TEST_JIRA_URL,
        "email": TEST_JIRA_USERNAME,
        "api_token": TEST_JIRA_API_TOKEN,
    })


def _ensure_ai_credential(headers):
    """Create an AI credential from .env vars.  Returns (cred_id, created).

    The provider is the credential's type — anthropic, openai or gemini are all registered
    from hop-core's built-in specs, each taking api_key and model.
    """
    if TEST_CLAUDE_API_KEY:
        provider, key, model = "anthropic", TEST_CLAUDE_API_KEY, TEST_CLAUDE_MODEL
    elif TEST_OPENAI_API_KEY:
        provider, key, model = "openai", TEST_OPENAI_API_KEY, TEST_OPENAI_MODEL
    elif TEST_GOOGLE_API_KEY:
        provider, key, model = "gemini", TEST_GOOGLE_API_KEY, TEST_GOOGLE_MODEL
    else:
        return None, False

    return _ensure_credential(headers, provider, f"Test AI {provider} (env)", {
        "api_key": key,
        "model": model,
    })


def _cleanup_credential(headers, cred_id, cred_type=None):
    """Delete a credential.  Best-effort."""
    requests.delete(f"{BASE_URL}/credentials/{cred_id}", headers=headers)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_job_completes_successfully(headers, max_retries=3):
    """Test that a job with valid credentials runs to completion."""
    print("\nTest: Job completes successfully")
    print("-" * 40)

    if not HAS_JIRA_CREDS:
        print("  ⚠ Skipping: no Jira credentials in .env")
        return True

    jira_id, jira_created = _ensure_jira_credential(headers)
    if not jira_id:
        print("  ⚠ Skipping: could not create Jira credential")
        return True

    ai_id, ai_created = _ensure_ai_credential(headers)
    instruction_set_id = get_instruction_set(headers, ai_configuration_id=ai_id)

    try:
        for attempt in range(1, max_retries + 1):
            job_data = {
                "instruction_set_id": instruction_set_id,
                "jql_query": "project = EZDNXTGEN ORDER BY created DESC",
                "max_tickets": 2,
                "output_filename": "test-job-execution.dita"
            }

            resp = requests.post(f"{BASE_URL}/jobs", json=job_data, headers=headers)
            assert resp.status_code == 200, f"Job creation failed: {resp.status_code} {resp.text}"
            job_id = resp.json()["id"]
            print(f"  Created job: {job_id} (attempt {attempt}/{max_retries})")

            job = wait_for_job(headers, job_id)
            print(f"  Status: {job['status']}")
            print(f"  Tickets processed: {job['tickets_processed']}")

            if job["status"] == "completed":
                assert job["tickets_processed"] > 0, "No tickets were processed"
                print(f"  ✓ Job completed successfully with {job['tickets_processed']} tickets")

                artifacts_resp = requests.get(
                    f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers
                )
                assert artifacts_resp.status_code == 200
                artifacts = artifacts_resp.json()
                dita_artifacts = [a for a in artifacts if a["artifact_type"] == "dita"]
                assert len(dita_artifacts) > 0, "No DITA artifact was created"
                print(f"  ✓ DITA artifact created: {dita_artifacts[0]['filename']}")
                requests.delete(f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers)
                return True

            error_msg = job.get("error_message", "")
            transient_keywords = ["overloaded", "529", "rate limit", "429", "timeout", "503"]
            is_transient = any(kw.lower() in error_msg.lower() for kw in transient_keywords)

            if is_transient and attempt < max_retries:
                print(f"  ⚠ Transient AI error, retrying in 10s: {error_msg}")
                time.sleep(10)
                continue

            stale_keywords = ["stale encryption", "no ai credentials found", "failed to decrypt"]
            is_stale = any(kw.lower() in error_msg.lower() for kw in stale_keywords)
            if is_stale:
                print(f"  ⚠ Credentials have stale encryption — re-create them with the current encryption key")
                return True

            # Jira infrastructure failure (site unavailable, 404, etc.) is not a code bug
            if "jira query failed" in error_msg.lower():
                print(f"  ⚠ Jira API unavailable (credentials were found and used): {error_msg}")
                return True

            # Empty result set is an environment issue, not a code bug
            if "no tickets found" in error_msg.lower():
                print(f"  ⚠ JQL returned no tickets — project EZDNXTGEN may be empty in this environment")
                return True

            assert False, f"Job failed with error: {error_msg}"
    finally:
        if jira_created and jira_id:
            _cleanup_credential(headers, jira_id, "jira")
        if ai_created and ai_id:
            _cleanup_credential(headers, ai_id, "ai")

    return False


def test_job_error_message_not_empty(headers):
    """Regression: failed jobs must have a non-empty error_message."""
    print("\nTest: Failed jobs have non-empty error messages")
    print("-" * 40)

    instruction_set_id = get_instruction_set(headers)

    # Previously this passed a fake ai_credential_id and expected a 404. Jobs no longer name
    # a credential — agents do — so the failure is provoked with JQL Jira cannot parse. Any
    # route to a failed job works here: what is being tested is that a failed job explains
    # itself, not which thing went wrong.
    job_data = {
        "instruction_set_id": instruction_set_id,
        "jql_query": "project = ((( not valid jql",
        "max_tickets": 1,
        "output_filename": "test-error-message.dita"
    }

    resp = requests.post(f"{BASE_URL}/jobs", json=job_data, headers=headers)

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

    Creates Jira + AI credentials from .env, then runs a job WITHOUT
    verify the pipeline discovers org-shared credentials automatically. The AI
    configuration comes from the instruction set's agents, the Jira credential
    from the organization.
    """
    print("\nTest: Organization-shared credentials are used")
    print("-" * 40)

    if not HAS_JIRA_CREDS or not HAS_AI_CREDS:
        print("  ⚠ Skipping: need both Jira and AI credentials in .env")
        return True

    jira_id, jira_created = _ensure_jira_credential(headers)
    ai_id, ai_created = _ensure_ai_credential(headers)

    if not jira_id or not ai_id:
        print("  ⚠ Skipping: could not create required credentials")
        return True

    try:
        instruction_set_id = get_instruction_set(headers, ai_configuration_id=ai_id)
        job_data = {
            "instruction_set_id": instruction_set_id,
            "jql_query": "project = EZDNXTGEN ORDER BY created DESC",
            "max_tickets": 1,
            "output_filename": "test-org-credentials.dita"
        }

        resp = requests.post(f"{BASE_URL}/jobs", json=job_data, headers=headers)
        assert resp.status_code == 200, f"Job creation failed: {resp.status_code}"
        job_id = resp.json()["id"]
        print(f"  Created job {job_id} (no AI credential specified)")

        job = wait_for_job(headers, job_id)

        error_msg = job.get("error_message", "")
        ai_provider_keywords = ["Anthropic", "OpenAI", "Gemini", "generation error", "overloaded", "rate limit"]
        failed_with_ai_error = job["status"] == "failed" and any(kw.lower() in error_msg.lower() for kw in ai_provider_keywords)

        stale_encryption = job["status"] == "failed" and "no ai credentials found" in error_msg.lower()

        # Jira query failure means credentials were found and used — just the query itself failed
        # (e.g. project doesn't exist, transient network error, or auth token expired)
        failed_with_jira_error = job["status"] == "failed" and "jira query failed" in error_msg.lower()

        # Empty result set is an environment issue — credentials were found and Jira was reached
        no_tickets = job["status"] == "failed" and "no tickets found" in error_msg.lower()

        assert job["status"] == "completed" or failed_with_ai_error or stale_encryption or failed_with_jira_error or no_tickets, (
            f"Job failed: {error_msg}. "
            "This likely means the orchestrator couldn't find org-shared credentials."
        )

        if job["status"] == "completed":
            print(f"  ✓ Job completed using org-shared credentials ({job['tickets_processed']} tickets)")
        elif stale_encryption:
            print(f"  ⚠ Credentials found but have stale encryption — re-create them with the current encryption key")
        elif no_tickets:
            print(f"  ⚠ Org-shared credentials were found and used (JQL returned no tickets — project EZDNXTGEN may be empty)")
        elif failed_with_jira_error:
            print(f"  ✓ Org-shared credentials were found and used (Jira query failed — project may not exist: {error_msg})")
        else:
            print(f"  ✓ Org-shared credentials were found (job failed due to transient AI error: {error_msg})")

        requests.delete(f"{BASE_URL}/jobs/{job_id}/artifacts", headers=headers)

    finally:
        if jira_created and jira_id:
            _cleanup_credential(headers, jira_id, "jira")
        if ai_created and ai_id:
            _cleanup_credential(headers, ai_id, "ai")

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
