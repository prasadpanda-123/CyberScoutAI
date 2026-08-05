"""
Unit tests for Flask Web Dashboard UI page routes with RBAC authentication.
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
        # Log in as seeded Super Admin user
        self.client.post("/login", data={"identifier": "admin@cyberscout.ai", "password": "Admin@CyberScout2026!"})

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated user is redirected to /login."""
        unauth_client = self.app.test_client()
        res = unauth_client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)

    def test_dashboard_index_route(self):
        """GET / — Overview dashboard page."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Executive Control Center", response.data)

    def test_opportunities_route(self):
        """GET /opportunities — Opportunities page."""
        response = self.client.get("/opportunities")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Opportunities Explorer", response.data)

    def test_analytics_route(self):
        """GET /analytics — Analytics page."""
        response = self.client.get("/analytics")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Intelligence & Growth Analytics", response.data)

    def test_collectors_route(self):
        """GET /collectors — Collectors status page."""
        response = self.client.get("/collectors")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Collectors Status & Controls", response.data)

    def test_scheduler_route(self):
        """GET /scheduler — Scheduler control page."""
        response = self.client.get("/scheduler")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Scheduler Control Center", response.data)

    def test_notifications_route(self):
        """GET /notifications — Email & Notification page."""
        response = self.client.get("/notifications")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Notification & Email Center", response.data)

    def test_configuration_route(self):
        """GET /configuration — Configuration editor page."""
        response = self.client.get("/configuration")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Configuration Editor", response.data)

    def test_logs_route(self):
        """GET /logs — Live log viewer page."""
        response = self.client.get("/logs")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Live Application Logs", response.data)


if __name__ == "__main__":
    unittest.main()
