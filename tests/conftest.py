"""Shared fixtures for integration tests."""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_BASE_URL, TEST_EMAIL, TEST_PASSWORD


@pytest.fixture(scope="session")
def headers():
    """Login and return authorization headers for API tests."""
    import requests

    resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10,
    )
    if resp.status_code != 200:
        pytest.skip(f"Cannot authenticate against {API_BASE_URL} (status {resp.status_code})")
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
