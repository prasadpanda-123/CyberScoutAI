"""
Unit tests for CyberScout AI branding and favicon integration.
Verifies all static image/favicon assets resolve and appear across templates.
"""

import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig


class TestBrandingIntegration(unittest.TestCase):

    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_static_brand_assets_exist(self):
        """Verify all brand images and favicon assets return HTTP 200."""
        assets = [
            "/static/images/cyberscout-logo.svg",
            "/static/images/cyberscout-logo.png",
            "/static/images/cyberscout-icon.png",
            "/static/images/cyberscout-icon.svg",
            "/static/favicon/favicon.ico",
            "/static/favicon/favicon-16x16.png",
            "/static/favicon/favicon-32x32.png",
            "/static/favicon/favicon-48x48.png",
            "/static/favicon/apple-touch-icon.png",
            "/static/favicon/favicon.svg",
        ]
        for path in assets:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Static asset missing or inaccessible: {path}")

    def test_login_page_branding(self):
        """Verify login page includes favicon tags and CyberScout AI icon."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("favicon-32x32.png", html)
        self.assertIn("cyberscout-icon.svg", html)

    def test_register_page_branding(self):
        """Verify registration page includes favicon tags and CyberScout AI icon."""
        res = self.client.get("/register")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("cyberscout-icon.svg", html)

    def test_forgot_password_page_branding(self):
        """Verify forgot password page includes favicon tags and CyberScout AI icon."""
        res = self.client.get("/forgot-password")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("cyberscout-icon.svg", html)

    def test_admin_login_page_branding(self):
        """Verify admin login page includes favicon tags and CyberScout AI icon."""
        res = self.client.get("/admin/login")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("cyberscout-icon.svg", html)

    def test_user_dashboard_branding(self):
        """Verify authenticated user dashboard contains favicon and updated sidebar icon."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "testanalyst"
            sess["role"] = "Analyst"

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("cyberscout-icon.svg", html)

    def test_user_profile_branding(self):
        """Verify authenticated user profile contains favicon and updated sidebar icon."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "testanalyst"
            sess["role"] = "Analyst"

        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("cyberscout-icon.svg", html)

    def test_admin_dashboard_branding(self):
        """Verify authenticated admin dashboard contains favicon and admin portal icon."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Administrator"

        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("favicon.ico", html)
        self.assertIn("cyberscout-icon.svg", html)


if __name__ == "__main__":
    unittest.main()
