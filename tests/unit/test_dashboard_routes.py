"""
Unit tests for Flask Web Dashboard UI page routes with isolated Admin RBAC authentication.
"""

import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestDashboardRoutes(unittest.TestCase):
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

        # Populate admin session namespace for test client
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Super Admin"
            sess["admin_csrf_token"] = "test_admin_csrf_token"

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated user is redirected to /login for protected user pages."""
        unauth_client = self.app.test_client()
        res_landing = unauth_client.get("/")
        self.assertEqual(res_landing.status_code, 200)

        res_dash = unauth_client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 302)
        self.assertIn("/login", res_dash.location)

    def test_dashboard_index_route(self):
        """GET /dashboard — Overview dashboard page."""
        self.client.post("/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!"})
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)

    def test_opportunities_route(self):
        """GET /opportunities — Opportunities page."""
        self.client.post("/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!"})
        response = self.client.get("/opportunities")
        self.assertEqual(response.status_code, 200)

    def test_analytics_route(self):
        """GET /analytics — Analytics page."""
        self.client.post("/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!"})
        response = self.client.get("/analytics")
        self.assertEqual(response.status_code, 200)

    def test_admin_collectors_route(self):
        """GET /admin/collectors — Admin Collectors status page."""
        response = self.client.get("/admin/collectors")
        self.assertEqual(response.status_code, 200)

    def test_admin_scheduler_route(self):
        """GET /admin/scheduler — Admin Scheduler control page."""
        response = self.client.get("/admin/scheduler")
        self.assertEqual(response.status_code, 200)

    def test_admin_configuration_route(self):
        """GET /admin/configuration — Admin Configuration editor page."""
        response = self.client.get("/admin/configuration")
        self.assertEqual(response.status_code, 200)

    def test_admin_logs_route(self):
        """GET /admin/logs — Admin Log viewer page."""
        response = self.client.get("/admin/logs")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
