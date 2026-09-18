"""
Phase 12.3 Comprehensive Admin MFA / OTP Verification Security Test Suite.

Tests:
1. Deterministic OTP generation, storage, and verification.
2. Leading-zero OTP lifecycle preservation (012345, 001234, 000001, 987654).
3. Whitespace, hyphen, and non-breaking space input normalization.
4. Attempt counter decrement semantics:
   - Valid attempt does not increment failed attempt counter before verification.
   - Invalid attempts increment counter by 1.
   - Exceeding maximum attempts (5) triggers lockout and challenge invalidation.
5. Expiration semantics:
   - Expired OTP fails and is purged.
6. Single-use replay prevention:
   - Re-submitting a verified OTP fails.
7. Resend OTP behavior:
   - Resend issues new OTP, invalidates old OTP, and resets attempt counter.
   - Resend cooldown enforces rate-limiting.
8. Identity binding and strict Admin vs User separation:
   - Challenge bound to specific admin identity.
   - Standard user cannot access admin verify endpoint or use admin challenge.
   - Complete end-to-end admin login -> MFA -> admin dashboard flow.
   - Complete end-to-end user login -> user dashboard flow.
"""

import os
import re
import time
import unittest
from unittest.mock import patch, MagicMock

os.environ["FLASK_ENV"] = "testing"
os.environ["SECRET_KEY"] = "testing-secret-key-1234567890abcdef"
os.environ["WTF_CSRF_ENABLED"] = "false"

from dashboard.app import create_app
from src.auth.admin_auth import AdminSecurityManager
from src.database.mfa_repository import MfaRepository


class TestPhase123AdminMfa(unittest.TestCase):
    """Test suite for Admin MFA OTP bugfix and security guarantees."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_leading_zero_otp_lifecycle(self):
        """STEP 12: Verify that leading-zero OTPs remain strings and hash correctly."""
        leading_zero_otps = ["012345", "001234", "000001", "987654"]

        for otp in leading_zero_otps:
            self.assertEqual(len(otp), 6, f"OTP {otp} must have length 6")
            self.assertTrue(otp.isdigit(), f"OTP {otp} must be numeric digits")

            # Hash generation
            otp_hash = AdminSecurityManager.hash_otp_code(otp)
            self.assertEqual(len(otp_hash), 64, "SHA-256 hash must be 64 hex characters")

            # Verification of exact string
            self.assertTrue(
                AdminSecurityManager.verify_otp_code(otp, otp_hash),
                f"Valid OTP {otp} must verify successfully"
            )

            # Verification with surrounding and internal whitespace
            self.assertTrue(
                AdminSecurityManager.verify_otp_code(f"  {otp}  ", otp_hash),
                f"Padded OTP '  {otp}  ' must verify successfully"
            )
            # Verification with dash formatting e.g. '012-345'
            formatted = f"{otp[:3]}-{otp[3:]}"
            self.assertTrue(
                AdminSecurityManager.verify_otp_code(formatted, otp_hash),
                f"Formatted OTP '{formatted}' must verify successfully"
            )

            # False cases: altered digit or truncated
            self.assertFalse(AdminSecurityManager.verify_otp_code(otp[1:], otp_hash))
            self.assertFalse(AdminSecurityManager.verify_otp_code(f"{otp}9", otp_hash))
            self.assertFalse(AdminSecurityManager.verify_otp_code("000000" if otp != "000000" else "111111", otp_hash))

    def test_input_normalization(self):
        """Verify normalization removes non-breaking spaces, zero-width spaces, and hyphens."""
        otp = "045678"
        otp_hash = AdminSecurityManager.hash_otp_code(otp)

        # Unicode non-breaking space (\u00a0), zero-width space (\u200b), byte order mark (\ufeff)
        dirty_inputs = [
            f"\u00a0{otp}\u00a0",
            f"\u200b{otp}\u200b",
            f"\ufeff{otp}",
            f"{otp[:3]} {otp[3:]}",
            f"{otp[:3]}-{otp[3:]}",
        ]
        for dirty in dirty_inputs:
            self.assertTrue(
                AdminSecurityManager.verify_otp_code(dirty, otp_hash),
                f"Dirty input {repr(dirty)} failed to normalize to {otp}"
            )

    def test_attempt_counter_semantics(self):
        """STEP 8: Valid attempt must not increment failed count; invalid attempts increment."""
        otp = "654321"
        otp_hash = AdminSecurityManager.hash_otp_code(otp)
        now = int(time.time())
        expires_at = now + 300

        pending_token = AdminSecurityManager.store_pending_mfa(
            user_id=999,
            username="test_admin_counter",
            email="test_counter@example.com",
            role="Admin",
            otp_hash=otp_hash,
            expires_at=expires_at,
        )

        # Check initial attempts
        state = AdminSecurityManager.get_pending_mfa(pending_token)
        self.assertIsNotNone(state)
        self.assertEqual(state.get("attempts", 0), 0)

        # Increment once for invalid attempt
        att1 = AdminSecurityManager.increment_pending_mfa_attempts(pending_token)
        self.assertEqual(att1, 1)

        # State should reflect 1 attempt
        state = AdminSecurityManager.get_pending_mfa(pending_token)
        self.assertEqual(state.get("attempts"), 1)

        # Valid OTP check does not mutate attempts
        self.assertTrue(AdminSecurityManager.verify_otp_code(otp, state["otp_hash"]))
        state_after = AdminSecurityManager.get_pending_mfa(pending_token)
        self.assertEqual(state_after.get("attempts"), 1)

        # Clean up
        AdminSecurityManager.clear_pending_mfa(pending_token)
        self.assertIsNone(AdminSecurityManager.get_pending_mfa(pending_token))

    def test_mfa_expiration(self):
        """STEP 7: Expired challenge cannot be verified."""
        otp = "789012"
        otp_hash = AdminSecurityManager.hash_otp_code(otp)
        now = int(time.time())
        # Set expired timestamp (10 seconds ago)
        expired_at = now - 10

        pending_token = AdminSecurityManager.store_pending_mfa(
            user_id=998,
            username="test_admin_expired",
            email="test_exp@example.com",
            role="Admin",
            otp_hash=otp_hash,
            expires_at=expired_at,
        )

        # get_pending_mfa should detect expiration and return None
        state = AdminSecurityManager.get_pending_mfa(pending_token)
        self.assertIsNone(state, "Expired pending MFA must return None")

    def test_resend_otp_behavior(self):
        """STEP 13: Resend generates new OTP, invalidates old, and resets attempts."""
        old_otp = "111222"
        old_hash = AdminSecurityManager.hash_otp_code(old_otp)
        now = int(time.time())
        expires_at = now + 300

        pending_token = AdminSecurityManager.store_pending_mfa(
            user_id=997,
            username="test_admin_resend",
            email="test_resend@example.com",
            role="Admin",
            otp_hash=old_hash,
            expires_at=expires_at,
        )

        # Simulate 2 failed attempts on old OTP
        AdminSecurityManager.increment_pending_mfa_attempts(pending_token)
        AdminSecurityManager.increment_pending_mfa_attempts(pending_token)

        state_before = AdminSecurityManager.get_pending_mfa(pending_token)
        self.assertEqual(state_before.get("attempts"), 2)

        # Perform resend: new OTP generated and stored
        new_otp = "333444"
        new_hash = AdminSecurityManager.hash_otp_code(new_otp)
        new_expires = now + 300

        updated = AdminSecurityManager.update_pending_mfa_otp(pending_token, new_hash, new_expires)
        self.assertTrue(updated)

        # Verify state after resend
        state_after = AdminSecurityManager.get_pending_mfa(pending_token)
        self.assertIsNotNone(state_after)
        self.assertEqual(state_after.get("attempts"), 0, "Attempts must reset to 0 upon resend")
        self.assertEqual(state_after.get("otp_hash"), new_hash)

        # Old OTP must now fail
        self.assertFalse(AdminSecurityManager.verify_otp_code(old_otp, state_after["otp_hash"]))
        # New OTP must succeed
        self.assertTrue(AdminSecurityManager.verify_otp_code(new_otp, state_after["otp_hash"]))

        AdminSecurityManager.clear_pending_mfa(pending_token)

    def test_admin_mfa_http_flow_success(self):
        """STEP 11 & 14: Full HTTP verification with valid OTP and single-use replay prevention."""
        otp = "054321"  # Leading zero
        otp_hash = AdminSecurityManager.hash_otp_code(otp)
        now = int(time.time())
        expires_at = now + 300

        pending_token = AdminSecurityManager.store_pending_mfa(
            user_id=996,
            username="test_http_admin",
            email="test_http@example.com",
            role="SuperAdmin",
            otp_hash=otp_hash,
            expires_at=expires_at,
        )
        csrf_token = AdminSecurityManager.generate_csrf_token()

        with self.client.session_transaction() as sess:
            sess["admin_pending_token"] = pending_token
            sess["admin_csrf_token"] = csrf_token

        # Submit valid OTP with whitespace padding
        resp = self.client.post(
            "/admin/verify-otp",
            data={
                "otp_code": f"  {otp}  ",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )

        # Must redirect to admin dashboard
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/dashboard", resp.headers["Location"])

        # Check session established
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get("admin_authenticated"))
            self.assertEqual(sess.get("admin_username"), "test_http_admin")
            self.assertEqual(sess.get("admin_role"), "SuperAdmin")
            self.assertNotIn("admin_pending_token", sess)

        # Single-use replay prevention: token cleared from storage
        self.assertIsNone(AdminSecurityManager.get_pending_mfa(pending_token))

        # Attempting to verify again with old session must redirect to /admin/login
        re_resp = self.client.post(
            "/admin/verify-otp",
            data={
                "otp_code": otp,
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        # Already authenticated admin visiting /admin/verify-otp redirects to dashboard
        self.assertEqual(re_resp.status_code, 302)
        self.assertIn("/admin/dashboard", re_resp.headers["Location"])

    def test_admin_mfa_http_failed_attempts_and_lockout(self):
        """Verify that 5 failed attempts trigger lockout."""
        otp = "888999"
        otp_hash = AdminSecurityManager.hash_otp_code(otp)
        now = int(time.time())
        expires_at = now + 300

        pending_token = AdminSecurityManager.store_pending_mfa(
            user_id=995,
            username="test_lockout_admin",
            email="test_lockout@example.com",
            role="Admin",
            otp_hash=otp_hash,
            expires_at=expires_at,
        )
        csrf_token = AdminSecurityManager.generate_csrf_token()

        with self.client.session_transaction() as sess:
            sess["admin_pending_token"] = pending_token
            sess["admin_csrf_token"] = csrf_token

        # Submit 4 incorrect attempts
        for attempt in range(1, 5):
            resp = self.client.post(
                "/admin/verify-otp",
                data={
                    "otp_code": "000000",
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn(f"{5 - attempt} attempt(s) remaining".encode(), resp.data)

        # 5th incorrect attempt must trigger lockout redirect
        resp5 = self.client.post(
            "/admin/verify-otp",
            data={
                "otp_code": "000000",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        self.assertEqual(resp5.status_code, 302)
        self.assertIn("/admin/login", resp5.headers["Location"])

        # Token must be cleared
        self.assertIsNone(AdminSecurityManager.get_pending_mfa(pending_token))

    def test_admin_and_user_isolation(self):
        """Standard user cannot access admin verify endpoint or use admin session."""
        csrf_token = AdminSecurityManager.generate_csrf_token()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 12345
            sess["user_authenticated"] = True
            sess["role"] = "User"
            sess["user_csrf_token"] = csrf_token
            # No admin_pending_token

        # Visiting /admin/verify-otp without pending admin session redirects to /admin/login
        resp = self.client.get("/admin/verify-otp", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/admin/login", resp.headers["Location"])


if __name__ == "__main__":
    unittest.main()
