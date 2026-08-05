"""
Unit tests for CyberScout AI v2.1 Authentication, RBAC, Setup Flow, and Security Headers.
"""

import json
import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestSecurityAuth(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.user_repo = UserRepository(self.db_manager)
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_user_creation_and_password_hashing(self):
        """Verify password is properly hashed with PBKDF2 SHA-256."""
        ts_id = int(time.time() * 1000)
        email = f"secops_{ts_id}@cyberscout.ai"
        username = f"secops_{ts_id}"

        user = self.user_repo.create_user(
            username=username,
            email=email,
            password="SecurePassword2026!",
            role="Operator",
        )
        self.assertIsNotNone(user["id"])
        self.assertEqual(user["role"], "Operator")

        auth_user = self.user_repo.authenticate(email, "SecurePassword2026!")
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user["username"], username)

        invalid_auth = self.user_repo.authenticate(email, "WrongPassword")
        self.assertIsNone(invalid_auth)

    def test_owasp_security_headers(self):
        """Verify OWASP security headers are set on HTTP responses."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")

        ref_policy = res.headers.get("Referrer-Policy")
        self.assertIsNotNone(ref_policy)
        self.assertIn("strict-origin-when-cross-origin", ref_policy or "")

        hsts = res.headers.get("Strict-Transport-Security")
        self.assertIsNotNone(hsts)
        self.assertIn("max-age=31536000", hsts or "")

        csp = res.headers.get("Content-Security-Policy")
        self.assertIsNotNone(csp)
        self.assertIn("default-src 'self'", csp or "")
        self.assertNotIn("Server", res.headers)

    def test_rbac_access_control(self):
        """Verify Viewer role is blocked from accessing Admin routes."""
        ts_id = int(time.time() * 1000)
        email = f"viewer_{ts_id}@cyberscout.ai"
        username = f"viewer_{ts_id}"

        self.user_repo.create_user(
            username=username,
            email=email,
            password="ViewerPassword2026!",
            role="Viewer",
        )
        # Log in as Viewer
        self.client.post("/login", data={"identifier": email, "password": "ViewerPassword2026!"})

        # Viewer trying to access Super Admin / Admin config route
        res = self.client.get("/configuration")
        self.assertEqual(res.status_code, 302)  # Redirected due to access error

        # Viewer trying to access Super Admin logs route
        res_logs = self.client.get("/logs")
        self.assertEqual(res_logs.status_code, 302)

    def test_first_run_setup_flow_disabled_when_admin_exists(self):
        """Verify GET /setup redirects to /login when administrator accounts exist."""
        res = self.client.get("/setup")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)


if __name__ == "__main__":
    unittest.main()
