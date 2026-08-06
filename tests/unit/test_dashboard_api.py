"""
Unit tests for Flask Web Dashboard REST API endpoints with auth checks.
"""

import json
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestDashboardAPI(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

        from src.database.user_repository import UserRepository
        repo = UserRepository()
        if not repo.get_by_email("admin@cyberscout.ai"):
            try:
                repo.create_user("admin", "admin@cyberscout.ai", "Admin@CyberScout2026!", "Super Admin")
            except Exception:
                pass

        # Log in normal user and admin session
        self.client.post("/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!"})
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"
            sess["admin_csrf_token"] = "test_admin_csrf_token"

    def test_api_unauthenticated_returns_401(self):
        """Verify unauthenticated API request returns 401 JSON error."""
        unauth_client = self.app.test_client()
        res = unauth_client.get("/api/stats", headers={"Accept": "application/json"})
        self.assertEqual(res.status_code, 401)
        data = json.loads(res.data)
        self.assertEqual(data.get("status"), "failed")

    def test_api_health_endpoint(self):
        """GET /api/health"""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("healthy", data)

    def test_api_stats_endpoint(self):
        """GET /api/stats"""
        res = self.client.get("/api/stats")
        self.assertEqual(res.status_code, 200)

    def test_api_opportunities_endpoint(self):
        """GET /api/opportunities"""
        res = self.client.get("/api/opportunities")
        self.assertEqual(res.status_code, 200)

    def test_admin_api_collectors_endpoint(self):
        """GET /admin/api/collectors"""
        res = self.client.get("/admin/api/collectors")
        self.assertEqual(res.status_code, 200)

    def test_admin_api_system_endpoint(self):
        """GET /admin/api/system"""
        res = self.client.get("/admin/api/system")
        self.assertEqual(res.status_code, 200)

    def test_admin_api_scheduler_pause_resume(self):
        """POST /admin/api/scheduler/pause and POST /admin/api/scheduler/resume"""
        res1 = self.client.post("/admin/api/scheduler/pause")
        self.assertEqual(res1.status_code, 200)
        res2 = self.client.post("/admin/api/scheduler/resume")
        self.assertEqual(res2.status_code, 200)


if __name__ == "__main__":
    unittest.main()
