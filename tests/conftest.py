import os
import pytest
from src.core.exceptions import ConfigurationError

test_db_url = os.getenv("TEST_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()

if test_db_url.startswith("sqlite") or not test_db_url:
    raise ConfigurationError("TEST_DATABASE_URL (or DATABASE_URL) environment variable pointing to a PostgreSQL database is required for tests. SQLite is not supported.")

os.environ["DATABASE_URL"] = test_db_url
os.environ["APP_ENV"] = "test"
os.environ["PYTEST_CURRENT_TEST"] = "1"
os.environ["EMAIL_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """
    Ensures all pytest tests use the configured PostgreSQL test database.
    """
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
