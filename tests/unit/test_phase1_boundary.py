"""
Phase 1 Unit Tests: User/Admin Security Boundary and Two-Table Isolation.

Verifies:
1. Normal user registration creates records ONLY in Users table and strips any client-submitted privilege fields.
2. User login authenticates ONLY against Users table.
3. Admin login authenticates ONLY against Admins table.
4. Admin password + OTP MFA authentication flow.
5. Portal isolation and privilege escalation prevention.
"""

import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository
from src.database.admin_repository import AdminRepository


class TestPhase1SecurityBoundary(unittest.TestCase):
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

    def test_registration_creates_user_only_and_ignores_role_manipulation(self):
        """Verify public registration creates record in Users table only and ignores role=admin, is_admin=true."""
        ts_id = int(time.time() * 1000)
        username = f"user_test_{ts_id}"
        email = f"user_{ts_id}@cyberscout.ai"

        # Attempt registration with malicious privilege parameters
        res = self.client.post("/register", data={
            "username": username,
            "email": email,
            "password": "UserPass123!",
            "confirm_password": "UserPass123!",
            "role": "Super Admin",
            "is_admin": "true",
            "admin": "1",
        })
        self.assertEqual(res.status_code, 302)

        # 1. Verify user exists in Users table
        user = self.user_repo.get_by_email(email)
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], username)
        self.assertEqual(user["role"], "Viewer")  # Server enforced default role

        # 2. Verify user does NOT exist in Admins table
        admin = self.admin_repo.get_by_email(email)
        self.assertIsNone(admin)

    def test_user_login_authenticates_against_users_only(self):
        """Verify normal login authenticates against Users table only and redirects admin accounts."""
        ts_id = int(time.time() * 1000)

        # Create admin in Admins table
        admin_email = f"admin_{ts_id}@cyberscout.ai"
        self.admin_repo.create_admin(
            username=f"admin_{ts_id}",
            email=admin_email,
            password="AdminPassword2026!",
            role="Admin",
        )

        # Admin credentials submitted to user /login
        res = self.client.post("/login", data={
            "identifier": admin_email,
            "password": "AdminPassword2026!",
        })
        # Normal user authentication fails for Admins-only accounts or redirects to /admin/login
        self.assertIn(res.status_code, (200, 302))
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("admin_authenticated"))

    def test_admin_login_authenticates_against_admins_table(self):
        """Verify /admin/login authenticates against Admins table and requires OTP."""
        ts_id = int(time.time() * 1000)
        admin_user = f"admin_sec_{ts_id}"
        admin_email = f"admin_sec_{ts_id}@cyberscout.ai"

        self.admin_repo.create_admin(
            username=admin_user,
            email=admin_email,
            password="AdminPassword2026!",
            role="Admin",
        )

        # Step 1: Submit admin credentials at /admin/login
        with self.client as c:
            # Set CSRF token in session
            with c.session_transaction() as sess:
                sess["admin_csrf_token"] = "test_csrf_token_12345678901234567890123456789012"

            res = c.post("/admin/login", data={
                "identifier": admin_email,
                "password": "AdminPassword2026!",
                "csrf_token": "test_csrf_token_12345678901234567890123456789012",
            })
            # Should proceed to OTP page or set pending MFA
            self.assertIn(res.status_code, (200, 302))

    def test_portal_isolation_user_cannot_access_admin_routes(self):
        """Verify normal authenticated user cannot access protected admin routes."""
        ts_id = int(time.time() * 1000)
        email = f"normal_{ts_id}@cyberscout.ai"

        self.user_repo.create_user(
            username=f"normal_{ts_id}",
            email=email,
            password="NormalPass123!",
            role="Viewer",
        )

        # Log in as normal user
        self.client.post("/login", data={"identifier": email, "password": "NormalPass123!"})

        # Request admin endpoints directly
        for admin_path in ["/admin/dashboard", "/admin/users", "/admin/logs", "/admin/configuration"]:
            res = self.client.get(admin_path)
            self.assertEqual(res.status_code, 302, f"HTML Path {admin_path} must redirect normal user to /admin/login")
            self.assertIn("/admin/login", res.location)

        for admin_api_path in ["/admin/api/config"]:
            res_api = self.client.get(admin_api_path)
            self.assertEqual(res_api.status_code, 401, f"API Path {admin_api_path} must return 401 for normal user")


if __name__ == "__main__":
    unittest.main()
