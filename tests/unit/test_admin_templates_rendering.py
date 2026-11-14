"""
Unit test verifying that all redesigned admin templates compile and render cleanly without Jinja syntax or runtime errors.
"""

import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager


class TestAdminTemplatesRendering(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_unauthenticated_admin_routes(self):
        """Verify login and verify-otp render HTTP 200 for visitors."""
        res_login = self.client.get("/admin/login?legacy=1")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Administrator Control Surface", res_login.data)

        # verify-otp with a valid pending mfa token
        import time
        from src.auth.admin_auth import AdminSecurityManager
        token = AdminSecurityManager.store_pending_mfa(
            user_id=1,
            username="test_admin",
            email="test@cyberscout.ai",
            role="Administrator",
            otp_hash="some_hashed_otp",
            expires_at=int(time.time()) + 300,
        )
        with self.client.session_transaction() as sess:
            sess["admin_pending_token"] = token

        res_otp = self.client.get("/admin/verify-otp?legacy=1")
        self.assertEqual(res_otp.status_code, 200)
        self.assertIn(b"Two-Factor Verification", res_otp.data)

    def test_authenticated_admin_pages_render_cleanly(self):
        """Verify all 16 authenticated admin pages compile and return HTTP 200 without Jinja errors."""
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user"] = "admin_tester"
            sess["admin_username"] = "admin_tester"
            sess["admin_role"] = "Administrator"
            sess["admin_user_id"] = 1
            sess["admin_csrf_token"] = "test_csrf_token_abc123"

        admin_routes = [
            ("/admin/dashboard", b"Operational Command Center"),
            ("/admin/collectors", b"AI Discovery &amp; Harvester Engines"),
            ("/admin/data-quality", b"Quality &amp; Free-Only Quarantine Center"),
            ("/admin/scheduler", b"Pipeline Scheduler &amp; Automation Hub"),
            ("/admin/users", b"User Administration &amp; RBAC"),
            ("/admin/configuration", b"Configuration &amp; Environment Safety"),
            ("/admin/reports", b"Reports &amp; Daily Excel Digests"),
            ("/admin/logs", b"Logs &amp; Security Audit Terminal"),
            ("/admin/source-health", b"Source Health &amp; Provider Registry"),
            ("/admin/analytics", b"Intelligence &amp; Operational Analytics"),
            ("/admin/diagnostics", b"System Diagnostics &amp; Live Probing"),
            ("/admin/system", b"System Specifications &amp; Environment"),
            ("/admin/email", b"Email &amp; Brevo Delivery Hub"),
            ("/admin/reliability", b"Reliability &amp; Disaster Recovery"),
        ]

        for route, expected_text in admin_routes:
            with self.subTest(route=route):
                with self.client.session_transaction() as sess:
                    sess["admin_authenticated"] = True
                    sess["admin_user"] = "admin_tester"
                    sess["admin_username"] = "admin_tester"
                    sess["admin_role"] = "Administrator"
                    sess["admin_user_id"] = 1
                    sess["admin_csrf_token"] = "test_csrf_token_abc123"

                res = self.client.get(route + "?legacy=1")
                self.assertEqual(
                    res.status_code,
                    200,
                    f"Route {route} failed with status {res.status_code}. Data: {res.data[:200]}"
                )
                self.assertIn(
                    expected_text,
                    res.data,
                    f"Expected text '{expected_text.decode()}' not found in response for {route}"
                )
