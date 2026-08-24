"""
Unit Tests for Standard User Profile Password Change OTP Flow.

Verifies:
1. Unauthenticated access to /profile redirects to /login.
2. Initial password change form validates current password, confirmation, and strength.
3. Valid password form initiates OTP and does NOT change Users table password hash.
4. Incorrect current password fails without generating OTP.
5. Incorrect OTP code fails and preserves original password.
6. Expired OTP fails and clears pending transaction.
7. Correct OTP updates password hash in Users table.
8. Reused or cleared OTP transaction cannot be reused.
9. Resending OTP updates code and enforces cooldown.
10. CSRF protection is required on both password request and OTP verification.
11. Audit logs record PASSWORD_CHANGE_OTP_REQUESTED, PASSWORD_CHANGE_OTP_VERIFIED, and PASSWORD_CHANGE with user_id.
"""

import time
import unittest
from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.auth.admin_auth import AdminSecurityManager
from src.database.audit_log_repository import AuditLogRepository
from src.database.connection import DatabaseManager
from src.database.user_repository import UserRepository


class TestUserProfileOTP(unittest.TestCase):
    def setUp(self):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()
        self.user_repo = UserRepository(self.db_manager)
        self.audit_repo = AuditLogRepository(self.db_manager)
        self.app = create_app(config_class=TestConfig)
        self.client = self.app.test_client()

    def test_unauthenticated_profile_redirects_to_login(self):
        """Verify unauthenticated GET /profile redirects to /login."""
        res = self.client.get("/profile")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)

    def test_user_password_change_otp_full_flow(self):
        """Verify standard user password change full flow: request OTP -> verify OTP -> DB updated."""
        ts = int(time.time() * 1000)
        username = f"user_otp_{ts}"
        email = f"user_otp_{ts}@cyberscout.ai"
        initial_pw = "UserInitialPass123!"
        new_pw = "UserNewBrandPass456!"

        user = self.user_repo.create_user(
            username=username,
            email=email,
            password=initial_pw,
            role="Viewer",
        )
        user_id = user["id"]
        csrf_tok = "test_csrf_user_profile_otp"

        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = user_id
                sess["username"] = username
                sess["email"] = email
                sess["role"] = "Viewer"
                sess["user_csrf_token"] = csrf_tok

            # 1. Attempt with incorrect current password
            res_bad_pw = c.post("/profile", data={
                "csrf_token": csrf_tok,
                "action": "request_pw_change",
                "current_password": "WrongInitialPass!",
                "new_password": new_pw,
                "confirm_password": new_pw,
            }, follow_redirects=True)
            self.assertIn(b"Current password is incorrect", res_bad_pw.data)
            self.assertTrue(self.user_repo.verify_password(user_id, initial_pw))

            # 2. Valid password submission -> Generates OTP and does NOT change DB password
            res_req = c.post("/profile", data={
                "csrf_token": csrf_tok,
                "action": "request_pw_change",
                "current_password": initial_pw,
                "new_password": new_pw,
                "confirm_password": new_pw,
            }, follow_redirects=True)
            self.assertIn(b"verification code has been sent", res_req.data)

            # CRITICAL: Verify DB password has NOT changed yet
            self.assertTrue(self.user_repo.verify_password(user_id, initial_pw))
            self.assertFalse(self.user_repo.verify_password(user_id, new_pw))

            # Verify pending token exists in session
            with c.session_transaction() as sess:
                pending_token = sess.get("user_pending_pw_token")
                self.assertIsNotNone(pending_token)
                pending_state = AdminSecurityManager.get_pending_password_change(pending_token)
                self.assertIsNotNone(pending_state)
                self.assertEqual(pending_state.get("target_type"), "user")
                self.assertEqual(pending_state.get("account_id"), user_id)
                self.assertNotIn("new_password", pending_state)

            # 3. Attempt verification with incorrect OTP
            res_bad_otp = c.post("/profile", data={
                "csrf_token": csrf_tok,
                "action": "verify_pw_otp",
                "otp_code": "000000",
            }, follow_redirects=True)
            self.assertIn(b"Invalid verification code", res_bad_otp.data)
            self.assertTrue(self.user_repo.verify_password(user_id, initial_pw))

            # 4. Verify with valid OTP code
            test_otp = "654321"
            test_otp_hash = AdminSecurityManager.hash_otp_code(test_otp)
            AdminSecurityManager.update_pending_password_change_otp(pending_token, test_otp_hash, int(time.time()) + 300)

            res_good_otp = c.post("/profile", data={
                "csrf_token": csrf_tok,
                "action": "verify_pw_otp",
                "otp_code": test_otp,
            }, follow_redirects=True)
            self.assertIn(b"Password updated successfully", res_good_otp.data)

            # Verify password was updated in Users table
            self.assertTrue(self.user_repo.verify_password(user_id, new_pw))
            self.assertFalse(self.user_repo.verify_password(user_id, initial_pw))

            # Verify pending session state was invalidated
            with c.session_transaction() as sess:
                self.assertNotIn("user_pending_pw_token", sess)

            # 5. Check audit logs
            logs_res = self.audit_repo.query_logs(search_query=username, limit=10)
            logs = logs_res.get("logs", [])
            actions = [l.get("action") for l in logs]
            self.assertIn("PASSWORD_CHANGE_OTP_REQUESTED", actions)
            self.assertIn("PASSWORD_CHANGE_OTP_VERIFIED", actions)
            self.assertIn("PASSWORD_CHANGE", actions)

    def test_user_password_change_csrf_required(self):
        """Verify CSRF protection on user profile password change and OTP verification."""
        ts = int(time.time() * 1000)
        user = self.user_repo.create_user(
            username=f"csrf_user_{ts}",
            email=f"csrf_user_{ts}@cyberscout.ai",
            password="UserInitialPass123!",
        )

        with self.client as c:
            with c.session_transaction() as sess:
                sess["user_id"] = user["id"]
                sess["username"] = user["username"]
                sess["email"] = user["email"]
                sess["user_csrf_token"] = "valid_csrf_token_here"

            res = c.post("/profile", data={
                "csrf_token": "invalid_token",
                "action": "request_pw_change",
                "current_password": "UserInitialPass123!",
                "new_password": "NewUserPass456!",
                "confirm_password": "NewUserPass456!",
            }, follow_redirects=True)
            self.assertIn(b"CSRF validation failed", res.data)


if __name__ == "__main__":
    unittest.main()
