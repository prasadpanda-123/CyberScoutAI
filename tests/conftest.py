"""
Pytest global configuration and environment isolation fixtures for CyberScout AI.
Ensures unit tests run against fast, isolated in-memory SQLite databases rather than cloud PostgreSQL.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """
    Automatically isolates all tests to use local in-memory SQLite database
    and testing configuration, preventing tests from reaching cloud database endpoints.
    """
    # Force SQLite in-memory for unit and integration test runs unless explicitly overridden
    if not os.getenv("USE_REAL_DB"):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///file:testdb?mode=memory&cache=shared&uri=true")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
