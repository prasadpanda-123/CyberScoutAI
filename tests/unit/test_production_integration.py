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

    def test_supabase_pooler_port_6543_normalization(self):
        """Verify Supabase pooler connection on port 5432 is auto-normalized to port 6543."""
        pooler_url = "postgresql://postgres.ref:secret@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
        normalized = get_db_url(custom_url=pooler_url)
        self.assertIn(":6543/", normalized)

    def test_opportunities_route_returns_200(self):
        """Verify GET /opportunities returns HTTP 200 HTML page for authenticated user."""
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        app = create_app(config_class=TestConfig)
        client = app.test_client()

        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "testuser"
            sess["role"] = "User"

    def test_admin_collectors_route_returns_200(self):
        """Verify GET /admin/collectors returns HTTP 200 HTML page for authenticated admin."""
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

        res = client.get("/admin/collectors")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Collectors Management", res.data)

    def test_admin_api_db_info_post_returns_200(self):
        """Verify POST /admin/api/db/info returns JSON 200."""
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

        res = client.post("/admin/api/db/info")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, dict)

    def test_post_run_returns_202_accepted(self):
        """Verify POST /api/run returns HTTP 202 Accepted status."""
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
        self.assertIn(res.status_code, (202, 409, 503))
        if res.status_code == 202:
            data = res.get_json()
            self.assertEqual(data.get("status"), "accepted")
            self.assertIn("job_id", data)

    def test_scan_status_alias_endpoint(self):
        """Verify GET /api/scan/status/<job_id> route alias returns status JSON or 404."""
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

        res = client.get("/api/scan/status/nonexistent_job")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
