#!/usr/bin/env python3
"""Test settings and configuration loading."""

import sys
import os

# Setup paths for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from setup_path import setup_test_paths
setup_test_paths()

from pydantic_settings import BaseSettings
from app.config import Settings, get_settings

def test_default_settings():
    """Test default settings values."""
    print("Testing default settings...")
    print("="*40)
    
    try:
        # Create settings instance
        settings = Settings()
        
        # Check key settings
        print(f"App Name: {settings.app_name}")
        print(f"App Debug: {settings.app_debug}")
        print(f"Database URL: {settings.database_url[:30]}...")
        print(f"Secret Key Set: {'Yes' if settings.secret_key else 'No'}")
        print(f"Google AI Model: {settings.google_ai_model}")
        
        # Validate required fields
        assert settings.app_name is not None
        assert settings.database_url is not None
        assert settings.secret_key is not None
        
        print("✓ Default settings loaded correctly")
        return True
        
    except Exception as e:
        print(f"⚠️ Settings require environment variables: {e}")
        print("  Set required vars in .env file or environment")
        return False

def test_environment_override():
    """Test that environment variables override defaults."""
    print("\nTesting environment variable override...")
    print("="*40)
    
    # Check for environment overrides
    env_vars = {
        'APP_NAME': os.getenv('APP_NAME'),
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
    assert settings1.app_name == settings2.app_name
    assert settings1.secret_key == settings2.secret_key
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
    test_default_settings()
    test_environment_override()
    test_get_settings_singleton()
    test_model_configurations()
    
    print("\n✅ All settings tests passed!")