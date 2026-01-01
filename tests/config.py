"""
Central configuration for all tests
"""

# API Configuration
API_BASE_URL = "http://localhost:8000/api/v1"

# Default test credentials
TEST_EMAIL = "admin@example.com"
TEST_PASSWORD = "admin123"

# Database Configuration (for direct DB tests)
DATABASE_URL = "postgresql://user:password@localhost:5432/release_notes_db"

# Test timeouts
DEFAULT_TIMEOUT = 30
LONG_TIMEOUT = 60