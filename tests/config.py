"""
Central configuration for all tests
"""
import requests
import psycopg2

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Default test credentials
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin123"
TEST_ORG_NAME = "Test Organization"

# Database Configuration (for direct DB tests)
DATABASE_URL = "postgresql://user:password@localhost:5432/release_notes_db"

# Test timeouts
DEFAULT_TIMEOUT = 30
LONG_TIMEOUT = 60


def ensure_test_account():
    """Ensure the default test account exists and is a superuser.

    Registers the account if it doesn't exist, then promotes it to
    superuser via direct DB access. Safe to call multiple times.
    """
    # Try to register (ignore if already exists)
    resp = requests.post(
        f"{API_BASE_URL}/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "organization_name": TEST_ORG_NAME,
        },
        timeout=10,
    )
    if resp.status_code not in (200, 400):
        raise RuntimeError(f"Failed to register test account: {resp.status_code} {resp.text}")

    # Promote to superuser
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_superuser = true WHERE email = %s",
                (TEST_EMAIL,),
            )
        conn.commit()
    finally:
        conn.close()

    # Verify login works
    resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Test account login failed after setup: {resp.status_code} {resp.text}"
        )