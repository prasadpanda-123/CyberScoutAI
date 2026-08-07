"""
Unit tests for Dashboard opportunities CSV/JSON exports with authentication.
"""

import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestDashboardExports(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()
        # Log in as standard user
        from src.database.user_repository import UserRepository
        repo = UserRepository()
        if not repo.get_by_email("testuser@cyberscout.ai"):
            try:
                repo.create_user("testuser", "testuser@cyberscout.ai", "UserPassword2026!", "User")
            except Exception:
                pass
        self.client.post("/login", data={"identifier": "testuser@cyberscout.ai", "password": "UserPassword2026!"})

    def test_export_csv_endpoint(self):
        """GET /opportunities/export/csv"""
        res = self.client.get("/opportunities/export/csv")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "text/csv")
        self.assertIn(b"Title,URL,Category", res.data)

    def test_export_json_endpoint(self):
        """GET /opportunities/export/json"""
        res = self.client.get("/opportunities/export/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "application/json")


if __name__ == "__main__":
    unittest.main()
