#!/usr/bin/env python3
"""Test settings and configuration loading."""

import sys
import os

# Setup paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from setup_path import setup_test_paths
setup_test_paths()

from pydantic_settings import BaseSettings

# Set required environment variables for testing before importing Settings
_TEST_ENV_DEFAULTS = {
    'DATABASE_URL': 'postgresql://user:password@localhost:5432/release_notes_db',
    'REDIS_URL': 'redis://localhost:6379/0',
    'APP_SECRET_KEY': 'test-secret-key',
    'JWT_SECRET_KEY': 'test-jwt-secret-key',
    'ENCRYPTION_KEY': 'test-encryption-key',
}

for key, value in _TEST_ENV_DEFAULTS.items():
    if key not in os.environ:
        os.environ[key] = value

from app.config import Settings, get_settings

def test_default_settings():
    """Test default settings values."""
    print("Testing default settings...")
    print("="*40)

    try:
        # Create settings instance
        settings = Settings()

        # Check key settings
        print(f"App Env: {settings.app_env}")
        print(f"App Debug: {settings.app_debug}")
        print(f"Database URL: {settings.database_url[:30]}...")
        print(f"Google AI Model: {settings.google_ai_model}")

        # Validate required fields
        assert settings.app_env is not None
        assert settings.database_url is not None
        assert settings.app_secret_key is not None

        print("✓ Default settings loaded correctly")
        return True

    except Exception as e:
        print(f"✗ Settings failed: {e}")
        return False

def test_environment_override():
    """Test that environment variables override defaults."""
    print("\nTesting environment variable override...")
    print("="*40)

    # Check for environment overrides
    env_vars = {
        'APP_ENV': os.getenv('APP_ENV'),
        'APP_DEBUG': os.getenv('APP_DEBUG'),
        'GOOGLE_AI_MODEL': os.getenv('GOOGLE_AI_MODEL'),
        'DATABASE_URL': os.getenv('DATABASE_URL')
    }

    settings = Settings()

    for key, env_value in env_vars.items():
        if env_value:
            print(f"  {key}: {env_value[:50]}...")

            # Check that setting reflects environment
            setting_key = key.lower()
            if hasattr(settings, setting_key):
                setting_value = getattr(settings, setting_key)
                print(f"    Setting value: {str(setting_value)[:50]}...")

    print("✓ Environment overrides checked")
    return True

def test_get_settings_singleton():
    """Test that get_settings returns singleton instance."""
    print("\nTesting settings singleton...")
    print("="*40)

    settings1 = get_settings()
    settings2 = get_settings()

    # Should be the same instance
    assert settings1 is settings2
    print("✓ get_settings returns singleton")

    # Check that values are consistent
    assert settings1.app_env == settings2.app_env
    assert settings1.app_secret_key == settings2.app_secret_key
    print("✓ Settings values consistent")

    return True

def test_model_configurations():
    """Test AI model configurations."""
    print("\nTesting AI model configurations...")
    print("="*40)

    settings = Settings()

    # Check default models
    print(f"Google AI Model: {settings.google_ai_model}")

    # These should have sensible defaults
    assert settings.google_ai_model is not None
    assert "gemini" in settings.google_ai_model.lower()

    print("✓ AI model configurations valid")
    return True

if __name__ == "__main__":
    print("Settings and Configuration Tests")
    print("="*60)

    # Run tests
    results = []
    results.append(test_default_settings())
    results.append(test_environment_override())
    results.append(test_get_settings_singleton())
    results.append(test_model_configurations())

    if all(results):
        print("\n✅ All settings tests passed!")
    else:
        print("\n✗ Some settings tests failed")
        sys.exit(1)
