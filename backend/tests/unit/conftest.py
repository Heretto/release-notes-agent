"""Unit test configuration.

Registers the app settings with hop-core so that security utilities
(set_auth_cookies, clear_auth_cookies, etc.) can call get_settings()
during unit tests without a running FastAPI app.
"""
import pytest
from hop_core.config import configure
from app.config import get_settings


def pytest_configure(config):
    configure(get_settings)
