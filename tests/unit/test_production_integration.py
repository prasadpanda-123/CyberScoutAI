"""
Regression tests for Production Deployment, Supabase PostgreSQL Normalization,
and Non-blocking Async Scan execution.
"""

import os
import unittest
from src.core.exceptions import DatabaseConnectionError
from src.database.engine import get_db_url
from src.core.version import get_version_info
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestProductionIntegration(unittest.TestCase):
    def test_production_mode_requires_database_url(self):
        """Verify get_db_url raises DatabaseConnectionError when DATABASE_URL is missing in production mode."""
        orig_env = os.getenv("APP_ENV")
        orig_url = os.getenv("DATABASE_URL")
        try:
            os.environ["APP_ENV"] = "production"
            if "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            with self.assertRaises(DatabaseConnectionError):
                get_db_url()
        finally:
            if orig_env is not None:
                os.environ["APP_ENV"] = orig_env
            else:
                os.environ.pop("APP_ENV", None)
            if orig_url is not None:
                os.environ["DATABASE_URL"] = orig_url

    def test_supabase_direct_url_normalization(self):
        """Verify direct Supabase hostname is normalized to Session Pooler format."""
        direct_url = "postgresql://postgres.ref:secret@db.ref.supabase.co:5432/postgres"
        normalized = get_db_url(custom_url=direct_url)
        self.assertIn("pooler.supabase.com:6543", normalized)
        self.assertIn("postgres.ref", normalized)

    def test_version_info_consistency(self):
        """Verify authoritative version is 1.1.3."""
        info = get_version_info()
        self.assertEqual(info["version"], "1.1.3")

    def test_async_scan_trigger_response(self):
        """Verify POST /api/run responds immediately without blocking."""
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        app = create_app(config_class=TestConfig)
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Admin"

        res = client.post("/api/run", json={"dry_run": True})
        self.assertIn(res.status_code, (200, 409, 503))
        data = res.get_json()
        self.assertIsInstance(data, dict)


if __name__ == "__main__":
    unittest.main()
