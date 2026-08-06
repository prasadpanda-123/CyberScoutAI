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

        # Log in as Super Admin via /admin/login
        self.client.get("/admin/login")
        with self.client.session_transaction() as sess:
            tok = sess.get("admin_csrf_token")
        self.client.post("/admin/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!", "csrf_token": tok})

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated user is redirected to /login for user pages."""
        unauth_client = self.app.test_client()
        res = unauth_client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)

    def test_dashboard_index_route(self):
        """GET / — Overview dashboard page."""
        # Also log in user session for public dashboard
        self.client.post("/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!"})
        response = self.client.get("/")
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
