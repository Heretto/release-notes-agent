#!/usr/bin/env python3
"""
Test AI provider credentials via the HTTP API.

Uses CLAUDE_DEFAULT_API_KEY and OPENAI_DEFAULT_API_KEY from the .env file
to create credentials, test the connection, and verify end-to-end functionality.
"""

import sys
import os
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD

# Load .env from project root for API keys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env'))

BASE_URL = API_BASE_URL


def get_auth_headers():
    """Login and return authorization headers."""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_ai_provider(headers, provider, name, api_key, model):
    """Create an AI credential, test it, verify success, and clean up.

    Returns (success, message) tuple.
    """
    print(f"\nTesting {provider.upper()} ({model})...")
    print("-" * 40)

    # Create credential
    create_resp = requests.post(
        f"{BASE_URL}/credentials/ai",
        json={
            "provider": provider,
            "name": name,
            "api_key": api_key,
            "model": model
        },
        headers=headers
    )

    if create_resp.status_code == 400 and "already exists" in create_resp.json().get("detail", ""):
        # Credential with this name already exists; find it
        list_resp = requests.get(f"{BASE_URL}/credentials/ai", headers=headers)
        cred_id = None
        for cred in list_resp.json():
            if cred["name"] == name:
                cred_id = cred["id"]
                break
        if not cred_id:
            return False, "Credential exists but not found in list"
        print(f"  Using existing credential: {cred_id}")
        created = False
    elif create_resp.status_code == 200:
        cred_id = create_resp.json()["id"]
        print(f"  Created credential: {cred_id}")
        created = True
    else:
        return False, f"Failed to create credential: {create_resp.status_code} {create_resp.text}"

    # Test the credential
    test_resp = requests.post(
        f"{BASE_URL}/credentials/{cred_id}/test",
        headers=headers
    )

    # Must not be 500
    if test_resp.status_code == 500:
        if created:
            requests.delete(f"{BASE_URL}/credentials/{cred_id}", headers=headers)
        return False, "Test endpoint returned 500 Internal Server Error"

    # Must not be 400 (decryption failure)
    if test_resp.status_code == 400:
        detail = test_resp.json().get("detail", "")
        if created:
            requests.delete(f"{BASE_URL}/credentials/{cred_id}", headers=headers)
        return False, f"Test endpoint returned 400: {detail}"

    if test_resp.status_code != 200:
        if created:
            requests.delete(f"{BASE_URL}/credentials/{cred_id}", headers=headers)
        return False, f"Test endpoint returned {test_resp.status_code}"

    data = test_resp.json()
    success = data.get("success", False)
    message = data.get("message", "No message")
    status_code = data.get("status_code", 0)

    print(f"  Response: success={success}, status={status_code}")
    print(f"  Message: {message}")

    # Clean up only if we created it
    if created:
        requests.delete(f"{BASE_URL}/credentials/{cred_id}", headers=headers)
        print(f"  Cleaned up credential")

    if success:
        print(f"  ✓ {provider.upper()} connection successful")
        return True, message
    else:
        return False, f"Connection failed (HTTP {status_code}): {message}"


def main():
    print("Configured AI Services Test")
    print("=" * 60)

    headers = get_auth_headers()
    print("✓ Authenticated")

    # Collect providers to test based on available API keys
    # Required providers (test fails if these don't work)
    required_providers = []
    # Optional providers (informational only)
    optional_providers = []

    claude_key = os.getenv("CLAUDE_DEFAULT_API_KEY")
    if claude_key:
        required_providers.append(("anthropic", "Claude Test", claude_key, "claude-sonnet-4-20250514"))
    else:
        print("\n  Skipping Anthropic: CLAUDE_DEFAULT_API_KEY not set")

    openai_key = os.getenv("OPENAI_DEFAULT_API_KEY")
    if openai_key:
        required_providers.append(("openai", "OpenAI Test", openai_key, "gpt-4o"))
    else:
        print("\n  Skipping OpenAI: OPENAI_DEFAULT_API_KEY not set")

    google_key = os.getenv("GOOGLE_AI_API_KEY")
    if google_key:
        optional_providers.append(("gemini", "Gemini Test", google_key, "gemini-2.0-flash"))

    all_providers = required_providers + optional_providers

    if not all_providers:
        print("\nNo AI API keys found. Set at least one of:")
        print("  CLAUDE_DEFAULT_API_KEY")
        print("  OPENAI_DEFAULT_API_KEY")
        print("  GOOGLE_AI_API_KEY")
        print("\nSkipping AI provider tests (no keys available)")
        return True  # Not a failure — just nothing to test

    # Test each provider
    print(f"\nTesting {len(all_providers)} configured AI service(s)...")
    print("=" * 60)

    results = []
    for provider, name, key, model in all_providers:
        success, message = test_ai_provider(headers, provider, name, key, model)
        is_required = any(p[0] == provider for p in required_providers)
        results.append((provider, success, message, is_required))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)

    required_pass = 0
    required_total = 0
    for provider, success, message, is_required in results:
        tag = "" if is_required else " (optional)"
        status = f"✓ Working{tag}" if success else f"✗ Failed{tag}: {message}"
        print(f"  {provider.upper()}: {status}")
        if is_required:
            required_total += 1
            if success:
                required_pass += 1

    working = sum(1 for _, s, _, _ in results if s)
    total = len(results)
    print(f"\nTotal: {working}/{total} services working")

    return required_pass == required_total


if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ All configured AI services tested successfully!")
    else:
        print("\n✗ Some AI services are not working correctly")
        sys.exit(1)
