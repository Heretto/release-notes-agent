"""Test configuration for tests under backend/tests/.

Registers app settings with hop-core and initializes the database engine
so that tests which import hop-core routes or use SessionLocal work correctly.
"""
import pytest
from hop_core.config import configure
from app.config import get_settings


def pytest_configure(config):
    configure(get_settings)
    settings = get_settings()
    from hop_core.db import init_engine
    init_engine(settings.database_url)
