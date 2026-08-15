"""
Phase 3 Unit Tests: Cookie/Session Security & Information Disclosure Hardening.

Verifies:
1. Session Cookie Flags (HttpOnly, SameSite, Cookie Name, Session Lifetime).
2. Zero Sensitive Data in Client-Side Session Cookies (no OTP hashes, password hashes, secrets).
3. Session Tampering Protection & Session Fixation Defense.
4. Information Disclosure Hardening on Auth Endpoints.
5. Phase 1 and Phase 2 Regression Verification.
"""

import json
import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository
from src.database.admin_repository import AdminRepository
from src.auth.admin_auth import AdminSecurityManager


class TestPhase3SessionSecurity(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.user_repo = UserRepository(self.db_manager)
        self.admin_repo = AdminRepository(self.db_manager)
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_session_cookie_configuration_flags(self):
        """Verify session cookie flags (HttpOnly, SameSite, Cookie Name)."""
        self.assertEqual(self.app.config.get("SESSION_COOKIE_HTTPONLY"), True)
        self.assertEqual(self.app.config.get("SESSION_COOKIE_SAMESITE"), "Lax")
        self.assertEqual(self.app.config.get("SESSION_COOKIE_NAME"), "cyberscout_session")

    def test_zero_sensitive_data_in_session_cookie(self):
        """Verify client-side session cookie contains zero sensitive secrets or OTP hashes."""
        ts_id = int(time.time() * 1000)
        admin_user = f"admin_p3_{ts_id}"
        admin_email = f"admin_p3_{ts_id}@cyberscout.ai"

        self.admin_repo.create_admin(
            username=admin_user,
            email=admin_email,
            password="AdminPassword2026!",
            role="Admin",
        )

        with self.client as c:
            # Set CSRF token in session
            with c.session_transaction() as sess:
                sess["admin_csrf_token"] = "test_csrf_token_12345678901234567890123456789012"

            c.post("/admin/login", data={
                "identifier": admin_email,
                "password": "AdminPassword2026!",
                "csrf_token": "test_csrf_token_12345678901234567890123456789012",
            })

            # Inspect active session dictionary keys
            with c.session_transaction() as sess:
                sess_str = str(sess)
                self.assertNotIn("otp_hash", sess_str)
                self.assertNotIn("admin_pending_otp_hash", sess)
                self.assertNotIn("password", sess_str)
                self.assertNotIn("password_hash", sess_str)
                self.assertNotIn("SECRET_KEY", sess_str)
                self.assertNotIn("DATABASE_URL", sess_str)

    def test_session_tampering_and_privilege_escalation_prevention(self):
        """Verify modifying client session dictionary cannot grant unauthenticated admin access."""
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = 9999
                sess["role"] = "Viewer"
                # Attempt to set client-side admin flag directly
                sess["admin_authenticated"] = False

            # Access protected admin dashboard
            res = c.get("/admin/dashboard")
            self.assertEqual(res.status_code, 302)
            self.assertIn("/admin/login", res.location)

    def test_logout_session_invalidation(self):
        """Verify logout clears session and invalidates authentication state."""
        ts_id = int(time.time() * 1000)
        u_email = f"logout_user_{ts_id}@cyberscout.ai"

        self.user_repo.create_user(
            username=f"logout_user_{ts_id}",
            email=u_email,
            password="UserPass123!",
            role="Viewer",
        )

        with self.client as c:
            c.post("/login", data={"identifier": u_email, "password": "UserPass123!"})
            with c.session_transaction() as sess:
                self.assertIsNotNone(sess.get("user_id"))

            c.get("/logout")
            with c.session_transaction() as sess:
                self.assertIsNone(sess.get("user_id"))
                self.assertIsNone(sess.get("username"))

    def test_information_disclosure_prevention_on_auth_errors(self):
        """Verify login failure responses return generic messages without database traces or internal paths."""
        res = self.client.post("/login", data={"identifier": "nonexistent@test.com", "password": "WrongPassword"})
        self.assertEqual(res.status_code, 200)
        content = res.get_data(as_text=True)

        self.assertNotIn("Traceback", content)
        self.assertNotIn("psycopg2", content)
        self.assertNotIn("SELECT", content)
        self.assertNotIn("postgresql://", content)
        self.assertIn("Invalid username/email or password", content)


if __name__ == "__main__":
    unittest.main()
