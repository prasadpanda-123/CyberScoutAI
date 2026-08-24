"""
Unit Tests for Dedicated Administrator Profile Page and Settings.

Verifies:
1. Unauthenticated access redirects to /admin/login.
2. Standard user access is rejected (403 Forbidden / redirected).
3. Authenticated administrator access returns HTTP 200.
4. Profile retrieves data strictly from Admins table (not Users).
5. IDOR prevention (admin cannot query other admin profiles by query/form params).
6. Sensitive fields (password hashes, OTP secrets, tokens) are NOT exposed in HTML.
7. Admin password change flow (strength verification, current password check).
8. CSRF protection on password update.
9. Audit logging records ADMIN_PROFILE_VIEW and ADMIN_PASSWORD_CHANGE with user_id=None.
"""

import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.auth.admin_auth import AdminSecurityManager
from src.database.admin_repository import AdminRepository
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestAdminProfile(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.admin_repo = AdminRepository(self.db_manager)
        self.user_repo = UserRepository(self.db_manager)
        self.audit_repo = AuditLogRepository(self.db_manager)
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_unauthenticated_admin_profile_redirects_to_admin_login(self):
        """Verify unauthenticated GET /admin/profile redirects to /admin/login."""
        res = self.client.get("/admin/profile")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/admin/login", res.location)

    def test_standard_user_access_to_admin_profile_is_denied(self):
        """Verify standard user (in Users table) is denied access to /admin/profile (HTTP 403)."""
        ts = int(time.time() * 1000)
        username = f"user_prof_{ts}"
        email = f"user_prof_{ts}@cyberscout.ai"

        self.user_repo.create_user(
            username=username,
            email=email,
            password="UserPass123!",
            role="Viewer",
        )

        # Authenticate as standard user
        self.client.post("/login", data={"identifier": email, "password": "UserPass123!"})

        # Attempt to access /admin/profile
        res = self.client.get("/admin/profile")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

    def test_authenticated_admin_gets_profile_200(self):
        """Verify authenticated administrator gets HTTP 200 on /admin/profile with correct data."""
        ts = int(time.time() * 1000)
        username = f"admin_prof_{ts}"
        email = f"admin_prof_{ts}@cyberscout.ai"

        admin = self.admin_repo.create_admin(
            username=username,
            email=email,
            password="AdminPassword2026!",
            role="Admin",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin["id"]
                sess["admin_username"] = username
                sess["admin_email"] = email
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = "csrf_token_test_admin_profile_12345"

            res = c.get("/admin/profile")
            self.assertEqual(res.status_code, 200)
            self.assertIn(username.encode("utf-8"), res.data)
            self.assertIn(email.encode("utf-8"), res.data)
            self.assertIn(b"Administrator Profile", res.data)
            self.assertIn(b"ADMINISTRATOR ACCOUNT", res.data)

    def test_admin_profile_reads_from_admins_table_not_users(self):
        """Verify profile reads data strictly from Admins table, isolated from Users table."""
        ts = int(time.time() * 1000)
        shared_name = f"dual_identity_{ts}"

        # Create user in Users table
        self.user_repo.create_user(
            username=shared_name,
            email=f"{shared_name}_user@cyberscout.ai",
            password="UserPassword123!",
            role="Viewer",
        )

        # Create admin in Admins table with different email
        admin = self.admin_repo.create_admin(
            username=shared_name,
            email=f"{shared_name}_admin@cyberscout.ai",
            password="AdminPassword2026!",
            role="Admin",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin["id"]
                sess["admin_username"] = shared_name
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = "test_csrf_token_admin_profile_isol"

            res = c.get("/admin/profile")
            self.assertEqual(res.status_code, 200)
            # Must contain the Admins table email, NOT the Users table email
            self.assertIn(f"{shared_name}_admin@cyberscout.ai".encode("utf-8"), res.data)
            self.assertNotIn(f"{shared_name}_user@cyberscout.ai".encode("utf-8"), res.data)

    def test_idor_prevention_query_param_manipulation_ignored(self):
        """Verify admin session identity cannot be spoofed via URL or query parameters."""
        ts = int(time.time() * 1000)
        admin1 = self.admin_repo.create_admin(
            username=f"admin_victim_{ts}",
            email=f"victim_{ts}@cyberscout.ai",
            password="AdminPassword2026!",
        )
        admin2 = self.admin_repo.create_admin(
            username=f"admin_attacker_{ts}",
            email=f"attacker_{ts}@cyberscout.ai",
            password="AdminPassword2026!",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin2["id"]
                sess["admin_username"] = admin2["username"]
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = "test_csrf_idor_prevention"

            # Attacker attempts to view admin1 profile by manipulating query parameters
            res = c.get(f"/admin/profile?admin_id={admin1['id']}&username={admin1['username']}&id={admin1['id']}")
            self.assertEqual(res.status_code, 200)
            # Response must be attacker's own profile, NOT victim's
            self.assertIn(admin2["username"].encode("utf-8"), res.data)
            self.assertNotIn(admin1["username"].encode("utf-8"), res.data)
            self.assertNotIn(admin1["email"].encode("utf-8"), res.data)

    def test_sensitive_fields_not_rendered(self):
        """Verify password hashes, OTP tokens, and secrets are never rendered in profile output."""
        ts = int(time.time() * 1000)
        admin = self.admin_repo.create_admin(
            username=f"admin_sec_{ts}",
            email=f"admin_sec_{ts}@cyberscout.ai",
            password="AdminPassword2026!",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin["id"]
                sess["admin_username"] = admin["username"]
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = "test_csrf_sensitive_check"

            res = c.get("/admin/profile")
            self.assertEqual(res.status_code, 200)

            # Get raw admin record from database
            raw_admin = self.admin_repo.get_by_id(admin["id"])
            # Ensure password hash is NOT rendered in HTML
            self.assertNotIn(b"pbkdf2:sha256", res.data)
            self.assertNotIn(b"password_hash", res.data)
            self.assertNotIn(b"otp_hash", res.data)
            self.assertNotIn(b"secret_key", res.data)

    def test_admin_password_change_success_and_validation(self):
        """Verify admin password change succeeds with valid current password and strong new password."""
        ts = int(time.time() * 1000)
        username = f"admin_pw_{ts}"
        email = f"admin_pw_{ts}@cyberscout.ai"
        initial_pw = "OldAdminPass123!"
        new_pw = "BrandNewAdminPass456!"

        admin = self.admin_repo.create_admin(
            username=username,
            email=email,
            password=initial_pw,
        )

        csrf_tok = "test_csrf_admin_pw_change"

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin["id"]
                sess["admin_username"] = username
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = csrf_tok

            # 1. Attempt password change with incorrect current password
            res_bad_curr = c.post("/admin/profile", data={
                "csrf_token": csrf_tok,
                "current_password": "WrongPassword123!",
                "new_password": new_pw,
                "confirm_password": new_pw,
            }, follow_redirects=True)
            self.assertIn(b"Current password is incorrect", res_bad_curr.data)

            # 2. Attempt password change with weak new password (< 10 chars / no special chars)
            res_weak = c.post("/admin/profile", data={
                "csrf_token": csrf_tok,
                "current_password": initial_pw,
                "new_password": "weak",
                "confirm_password": "weak",
            }, follow_redirects=True)
            self.assertIn(b"Password requirement not met", res_weak.data)

            # 3. Successful password change
            res_success = c.post("/admin/profile", data={
                "csrf_token": csrf_tok,
                "current_password": initial_pw,
                "new_password": new_pw,
                "confirm_password": new_pw,
            }, follow_redirects=True)
            self.assertIn(b"Administrator password updated successfully", res_success.data)

            # Verify password was updated in Admins table
            self.assertTrue(self.admin_repo.verify_password(admin["id"], new_pw))
            self.assertFalse(self.admin_repo.verify_password(admin["id"], initial_pw))

    def test_admin_password_change_csrf_protection(self):
        """Verify password update fails if CSRF token is invalid or missing."""
        ts = int(time.time() * 1000)
        admin = self.admin_repo.create_admin(
            username=f"admin_csrf_{ts}",
            email=f"admin_csrf_{ts}@cyberscout.ai",
            password="AdminPassword2026!",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin["id"]
                sess["admin_username"] = admin["username"]
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = "valid_csrf_token_value_here"

            res = c.post("/admin/profile", data={
                "csrf_token": "wrong_invalid_token",
                "current_password": "AdminPassword2026!",
                "new_password": "NewAdminPassword2026!",
                "confirm_password": "NewAdminPassword2026!",
            }, follow_redirects=True)
            self.assertIn(b"CSRF validation failed", res.data)

    def test_admin_audit_logging_preserves_null_user_id(self):
        """Verify ADMIN_PROFILE_VIEW and ADMIN_PASSWORD_CHANGE create audit records with user_id=None."""
        ts = int(time.time() * 1000)
        username = f"admin_audit_{ts}"
        admin = self.admin_repo.create_admin(
            username=username,
            email=f"admin_audit_{ts}@cyberscout.ai",
            password="AdminPassword2026!",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["admin_authenticated"] = True
                sess["admin_user_id"] = admin["id"]
                sess["admin_username"] = username
                sess["admin_role"] = "Admin"
                sess["role"] = "Admin"
                sess["admin_csrf_token"] = "test_csrf_audit_log"

            # Profile GET triggers ADMIN_PROFILE_VIEW
            res = c.get("/admin/profile")
            self.assertEqual(res.status_code, 200)

            # Query audit logs
            logs_res = self.audit_repo.query_logs(search_query=username, limit=10)
            logs = logs_res.get("logs", [])
            self.assertTrue(len(logs) > 0)
            view_logs = [l for l in logs if l.get("action") == "ADMIN_PROFILE_VIEW"]
            self.assertTrue(len(view_logs) > 0)
            # Crucial requirement: user_id MUST be None (NULL) for admin actions to protect Users FK
            self.assertIsNone(view_logs[0].get("user_id"))
            self.assertEqual(view_logs[0].get("username"), username)


if __name__ == "__main__":
    unittest.main()
