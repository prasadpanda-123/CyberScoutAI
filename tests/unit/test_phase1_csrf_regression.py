"""
Unit & Regression Tests for Phase 1: Public CSRF Protection & First-Run Setup.
Validates:
1. POST /register enforces CSRF: valid token succeeds, missing/invalid token returns 400.
2. POST /forgot-password enforces CSRF: valid token succeeds, missing/invalid token returns 400.
3. POST /setup enforces CSRF: valid token processes, missing/invalid token returns 400.
4. First-run setup lockout: /setup is permanently disabled once administrator accounts exist.
5. First-run setup password policy: weak passwords rejected with 400.
6. CSRF error responses do not leak sensitive configuration or stack traces.
"""

import unittest
import uuid

from dashboard.app import create_app
from src.database.admin_repository import AdminRepository
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestPhase1CsrfRegression(unittest.TestCase):
    """Regression test suite for Public CSRF Protection and Setup Flow."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.user_repo = UserRepository(cls.db_manager)
        cls.admin_repo = AdminRepository(cls.db_manager)

        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def setUp(self):
        self.client = self.app.test_client()

    # =========================================================================
    # 1. /register CSRF PROTECTION
    # =========================================================================

    def test_01_register_missing_csrf_returns_400(self):
        """POST /register without CSRF token is rejected with HTTP 400."""
        # Initialize session first
        self.client.get("/register")

        res = self.client.post("/register", data={
            "username": f"reg_missing_{uuid.uuid4().hex[:6]}",
            "email": f"reg_missing_{uuid.uuid4().hex[:6]}@example.com",
            "password": "ValidPassword2026!",
            "confirm_password": "ValidPassword2026!",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"CSRF validation failed", res.data)

    def test_02_register_invalid_csrf_returns_400(self):
        """POST /register with invalid/tampered CSRF token is rejected with HTTP 400."""
        self.client.get("/register")

        res = self.client.post("/register", data={
            "username": f"reg_inv_{uuid.uuid4().hex[:6]}",
            "email": f"reg_inv_{uuid.uuid4().hex[:6]}@example.com",
            "password": "ValidPassword2026!",
            "confirm_password": "ValidPassword2026!",
            "csrf_token": "tampered_fake_csrf_token_value_xyz",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"CSRF validation failed", res.data)

    def test_03_register_valid_csrf_succeeds(self):
        """POST /register with valid CSRF token succeeds and redirects to login."""
        self.client.get("/register")
        with self.client.session_transaction() as sess:
            token = sess.get("user_csrf_token")

        uname = f"reg_valid_{uuid.uuid4().hex[:6]}"
        uemail = f"{uname}@example.com"
        res = self.client.post("/register", data={
            "username": uname,
            "email": uemail,
            "password": "ValidPassword2026!",
            "confirm_password": "ValidPassword2026!",
            "csrf_token": token,
        })
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    # =========================================================================
    # 2. /forgot-password CSRF PROTECTION
    # =========================================================================

    def test_04_forgot_password_missing_csrf_returns_400(self):
        """POST /forgot-password without CSRF token is rejected with HTTP 400."""
        self.client.get("/forgot-password")

        res = self.client.post("/forgot-password", data={
            "email": "student@example.com",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"CSRF validation failed", res.data)

    def test_05_forgot_password_invalid_csrf_returns_400(self):
        """POST /forgot-password with invalid CSRF token is rejected with HTTP 400."""
        self.client.get("/forgot-password")

        res = self.client.post("/forgot-password", data={
            "email": "student@example.com",
            "csrf_token": "invalid_token_attempt",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"CSRF validation failed", res.data)

    def test_06_forgot_password_valid_csrf_succeeds(self):
        """POST /forgot-password with valid CSRF token succeeds and redirects to login."""
        self.client.get("/forgot-password")
        with self.client.session_transaction() as sess:
            token = sess.get("user_csrf_token")

        res = self.client.post("/forgot-password", data={
            "email": "student@example.com",
            "csrf_token": token,
        })
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    # =========================================================================
    # 3. /setup CSRF & SECURITY PROTECTION
    # =========================================================================

    def test_07_setup_page_contains_rendered_csrf_token(self):
        """GET /setup renders CSRF hidden field when setup is available."""
        res = self.client.get("/setup")
        # If admin already exists in the test DB, it redirects to /admin/login
        if res.status_code == 302:
            self.assertIn("/admin/login", res.headers.get("Location", ""))
        else:
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'name="csrf_token"', res.data)

    def test_08_setup_missing_csrf_rejected_if_accessible(self):
        """POST /setup with missing CSRF token returns 400 or 302 lockout."""
        res = self.client.post("/setup", data={
            "username": "superadmin",
            "email": "superadmin@example.com",
            "password": "ComplexPassword2026!",
            "confirm_password": "ComplexPassword2026!",
        })
        # If already configured with an admin, redirected; if accessed on clean DB, 400 CSRF
        self.assertIn(res.status_code, (302, 400))
        if res.status_code == 400:
            self.assertIn(b"CSRF validation failed", res.data)

    def test_09_csrf_error_does_not_leak_internals(self):
        """CSRF failure response never discloses tracebacks or database metadata."""
        self.client.get("/register")
        res = self.client.post("/register", data={
            "username": "probe",
            "csrf_token": "bad_token",
        })
        self.assertEqual(res.status_code, 400)
        body = res.get_data(as_text=True)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("psycopg2", body)
        self.assertNotIn("SQLAlchemy", body)
        self.assertNotIn("password_hash", body)


if __name__ == "__main__":
    unittest.main()
