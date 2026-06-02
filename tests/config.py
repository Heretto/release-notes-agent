"""
Central configuration for all tests.

Credentials for integration tests are loaded from the project-root .env file.
"""
import os
import requests
import psycopg2

from dotenv import load_dotenv

# Load .env from project root (one level above tests/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_project_root, ".env"))

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

# ---------------------------------------------------------------------------
# Integration test credentials (from .env)
# ---------------------------------------------------------------------------

# Jira
TEST_JIRA_URL = os.getenv("TEST_JIRA_URL")
TEST_JIRA_USERNAME = os.getenv("TEST_JIRA_USERNAME")
TEST_JIRA_API_TOKEN = os.getenv("TEST_JIRA_API_TOKEN")
HAS_JIRA_CREDS = all([TEST_JIRA_URL, TEST_JIRA_USERNAME, TEST_JIRA_API_TOKEN])

# AI providers
TEST_CLAUDE_API_KEY = os.getenv("TEST_CLAUDE_API_KEY")
TEST_CLAUDE_MODEL = os.getenv("TEST_CLAUDE_MODEL", "claude-haiku-4-5-20251001")
TEST_OPENAI_API_KEY = os.getenv("TEST_OPENAI_API_KEY")
TEST_OPENAI_MODEL = os.getenv("TEST_OPENAI_MODEL", "gpt-4o")
TEST_GOOGLE_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
TEST_GOOGLE_MODEL = os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash")
HAS_AI_CREDS = any([TEST_CLAUDE_API_KEY, TEST_OPENAI_API_KEY, TEST_GOOGLE_API_KEY])

# Heretto
TEST_HERETTO_SERVER = os.getenv("TEST_HERETTO_SERVER") or os.getenv("HERETTO_TESTING_SERVER")
TEST_HERETTO_USER = os.getenv("TEST_HERETTO_LOGIN_USER") or os.getenv("HERETTO_TESTING_LOGIN_USER")
TEST_HERETTO_TOKEN = os.getenv("TEST_HERETTO_LOGIN_TOKEN") or os.getenv("HERETTO_TESTING_LOGIN_TOKEN")
HAS_HERETTO_CREDS = all([TEST_HERETTO_SERVER, TEST_HERETTO_USER, TEST_HERETTO_TOKEN])


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
