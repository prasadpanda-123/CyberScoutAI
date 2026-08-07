import os
import pytest

# Enforce root-level test environment isolation before module imports
if not os.getenv("USE_REAL_DB"):
    os.environ["DATABASE_URL"] = "sqlite:///file:testdb?mode=memory&cache=shared&uri=true"
os.environ["APP_ENV"] = "test"
os.environ["PYTEST_CURRENT_TEST"] = "1"
os.environ["EMAIL_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """
    Automatically isolates all tests to use local in-memory SQLite database
    and testing configuration, preventing tests from reaching cloud database endpoints.
    """
    if not os.getenv("USE_REAL_DB"):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///file:testdb?mode=memory&cache=shared&uri=true")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
