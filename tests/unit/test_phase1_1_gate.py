"""
Comprehensive Gate & Regression Test Suite for CyberScout AI Phase 1.1.

Validates:
- SEC-01: Open Redirect Defense across Login, MFA, and OTP Verification stages.
- SEC-02: Backend CSRF Protection on POST /admin/users.
- SEC-03: Backend CSRF Protection on Legacy Administrative Mutations under /api/*.
- SeedManager Idempotency against pre-populated / initialized databases.
- PostgreSQL Transaction Safety and Error Recovery.
- URL Hash Uniqueness and Conflict Resolution.
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.auth.admin_auth import AdminSecurityManager
from src.database.admin_repository import AdminRepository
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.seed import SeedManager
from src.models.opportunity import Opportunity
from src.utils.url_utils import is_safe_internal_url


class TestPhase11Gate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class TestConfig(DashboardConfig):
            TESTING = True
            DEBUG = False

        cls.app = create_app(config_class=TestConfig)
        cls.db_mgr = DatabaseManager()
        cls.db_mgr.initialize_database()

    def setUp(self):
        self.client = self.app.test_client()
        self.admin_repo = AdminRepository(db_manager=self.db_mgr)
        self.opp_repo = OpportunityRepository(db_manager=self.db_mgr)

    # =========================================================================
    # SEC-01: OPEN REDIRECT DEFENSE
    # =========================================================================

    def test_sec01_url_utility_boundary(self):
        """Verify is_safe_internal_url strictly discriminates safe relative paths from attacks."""
        # Malicious variants must ALL be rejected
        evil_urls = [
            "https://attacker.example",
            "http://attacker.example",
            "//attacker.example",
            "//attacker.example/path",
            "https://attacker.example/path?evil=1",
            "javascript:alert(1)",
            "javascript://attacker.example",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            r"\attacker.example",
            r"/\attacker.example",
            r"/\\attacker.example",
            r"\\attacker.example",
            "/%2f/attacker.example",
            "/%5cattacker.example",
            "/path\nLocation: https://attacker.example",
            "/path\r\nLocation: https://attacker.example",
            "",
            None,
            "   ",
        ]
        for evil in evil_urls:
            self.assertFalse(is_safe_internal_url(evil), f"Failed to reject dangerous URL: {evil}")

        # Safe internal destinations must be accepted
        safe_urls = [
            "/",
            "/admin/dashboard",
            "/admin/opportunities?page=2",
            "/dashboard",
            "/opportunities",
            "/analytics?period=30d",
        ]
        for safe in safe_urls:
            self.assertTrue(is_safe_internal_url(safe), f"Rejected safe relative URL: {safe}")

    def test_sec01_admin_login_mfa_open_redirect_complete_flow(self):
        """
        SEC-01 End-to-End:
        GET /admin/login?next=<evil> -> POST /admin/login -> /admin/verify-otp -> final redirect.
        Must NEVER redirect to an external destination.
        """
        evil_target = "https://attacker.example/steal"
        ts = int(time.time() * 1000)
        uname = f"gate_adm_{ts}"
        email = f"{uname}@cyberscout.ai"
        pwd = "AdminGatePass2026!"

        self.admin_repo.create_admin(username=uname, email=email, password=pwd, role="Admin")

        # 1. GET /admin/login with malicious ?next=
        get_res = self.client.get(f"/admin/login?next={evil_target}")
        self.assertEqual(get_res.status_code, 200)
        # Verify malicious next is NOT rendered into the form DOM
        self.assertNotIn(evil_target, get_res.get_data(as_text=True))

        with self.client.session_transaction() as sess:
            csrf_tok = sess.get("admin_csrf_token")

        # 2. POST credentials with malicious next parameter
        with patch("src.auth.admin_auth.AdminSecurityManager.generate_otp_code", return_value="654321"):
            post_res = self.client.post(
                "/admin/login",
                data={
                    "admin_username": uname,
                    "admin_password": pwd,
                    "csrf_token": csrf_tok,
                    "next": evil_target,
                },
                follow_redirects=False,
            )
            self.assertEqual(post_res.status_code, 302)
            self.assertIn("/admin/verify-otp", post_res.location)

            with self.client.session_transaction() as sess:
                otp_csrf = sess.get("admin_csrf_token")
                # Ensure stored next_url in session/mfa was sanitized to internal default
                stored_next = sess.get("admin_pending_next")
                if stored_next:
                    self.assertNotIn("attacker.example", stored_next)

            # 3. POST valid OTP to complete MFA
            otp_res = self.client.post(
                "/admin/verify-otp",
                data={
                    "otp_code": "654321",
                    "csrf_token": otp_csrf,
                },
                follow_redirects=False,
            )
            self.assertEqual(otp_res.status_code, 302)
            # CRITICAL INVARIANT: Final redirect MUST NOT go to attacker.example
            self.assertNotIn("attacker.example", otp_res.location)
            self.assertIn("/admin/dashboard", otp_res.location)

    def test_sec01_admin_login_safe_next_preservation(self):
        """Verify safe internal next destination is properly preserved across MFA."""
        safe_target = "/admin/opportunities?page=2"
        ts = int(time.time() * 1000)
        uname = f"gate_safe_{ts}"
        email = f"{uname}@cyberscout.ai"
        pwd = "AdminGatePass2026!"

        self.admin_repo.create_admin(username=uname, email=email, password=pwd, role="Admin")

        with self.client.session_transaction() as sess:
            csrf_tok = "admin_gate_csrf_1"
            sess["admin_csrf_token"] = csrf_tok

        with patch("src.auth.admin_auth.AdminSecurityManager.generate_otp_code", return_value="112233"):
            post_res = self.client.post(
                "/admin/login",
                data={
                    "admin_username": uname,
                    "admin_password": pwd,
                    "csrf_token": csrf_tok,
                    "next": safe_target,
                },
                follow_redirects=False,
            )
            self.assertEqual(post_res.status_code, 302)

            with self.client.session_transaction() as sess:
                otp_csrf = sess.get("admin_csrf_token")

            otp_res = self.client.post(
                "/admin/verify-otp",
                data={"otp_code": "112233", "csrf_token": otp_csrf},
                follow_redirects=False,
            )
            self.assertEqual(otp_res.status_code, 302)
            self.assertEqual(otp_res.location, safe_target)

    # =========================================================================
    # SEC-02: ADMIN USER CREATION CSRF
    # =========================================================================

    def test_sec02_admin_user_creation_csrf_protection(self):
        """
        SEC-02: Inspect POST /admin/users
        1. Valid CSRF -> accepted
        2. Missing CSRF -> rejected (403)
        3. Invalid CSRF -> rejected (403)
        """
        admin_client = self.app.test_client()
        csrf_tok = "sec02_admin_csrf_token_secret"

        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Administrator"
            sess["admin_csrf_token"] = csrf_tok

        ts = int(time.time() * 1000)

        # 1. Missing CSRF -> MUST RETURN 403
        res_missing = admin_client.post(
            "/admin/users",
            data={
                "action": "create_user",
                "username": f"user_nocsrf_{ts}",
                "email": f"user_nocsrf_{ts}@example.com",
                "password": "Password123!",
                "role": "Viewer",
            },
        )
        self.assertEqual(res_missing.status_code, 403)

        # 2. Invalid CSRF -> MUST RETURN 403
        res_invalid = admin_client.post(
            "/admin/users",
            data={
                "action": "create_user",
                "username": f"user_badcsrf_{ts}",
                "email": f"user_badcsrf_{ts}@example.com",
                "password": "Password123!",
                "role": "Viewer",
                "csrf_token": "wrong_csrf_token_value",
            },
        )
        self.assertEqual(res_invalid.status_code, 403)

        # 3. Valid CSRF -> Accepted (200 OK HTML with user created or flash message)
        res_valid = admin_client.post(
            "/admin/users",
            data={
                "action": "create_user",
                "username": f"user_valid_{ts}",
                "email": f"user_valid_{ts}@example.com",
                "password": "Password123!",
                "role": "Viewer",
                "csrf_token": csrf_tok,
            },
        )
        self.assertEqual(res_valid.status_code, 200)
        self.assertIn(f"user_valid_{ts}", res_valid.get_data(as_text=True))

    # =========================================================================
    # SEC-03: LEGACY ADMIN API CSRF ENFORCEMENT (/api/*)
    # =========================================================================

    def test_sec03_legacy_admin_api_csrf_mutations(self):
        """
        SEC-03: Audit every legacy administrative mutation under /api/*.
        Endpoints:
          - /api/run
          - /api/email/test
          - /api/scheduler/pause
          - /api/scheduler/resume
          - /api/scheduler/restart
          - /api/report/trigger
          - /api/opportunities/clear-old
          - /api/analytics/refresh
        Verify that missing or invalid CSRF returns HTTP 403, and valid CSRF is accepted.
        """
        endpoints = [
            ("/api/run", {"dry_run": True}),
            ("/api/email/test", {}),
            ("/api/scheduler/pause", {}),
            ("/api/scheduler/resume", {}),
            ("/api/scheduler/restart", {}),
            ("/api/report/trigger", {}),
            ("/api/opportunities/clear-old", {"days": 30}),
            ("/api/analytics/refresh", {}),
        ]

        admin_client = self.app.test_client()
        valid_csrf = "legacy_api_csrf_token_secret_999"

        with admin_client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_username"] = "admin"
            sess["admin_role"] = "Admin"
            sess["admin_csrf_token"] = valid_csrf

        for path, payload in endpoints:
            with self.subTest(endpoint=path):
                # A. Missing CSRF -> MUST RETURN 403
                res_no_csrf = admin_client.post(path, json=payload)
                self.assertEqual(
                    res_no_csrf.status_code, 403,
                    f"Endpoint {path} failed to reject request missing CSRF"
                )
                self.assertEqual(res_no_csrf.get_json().get("error"), "CSRF token validation failed")

                # B. Invalid CSRF -> MUST RETURN 403
                bad_payload = dict(payload)
                bad_payload["csrf_token"] = "invalid_token_xyz"
                res_bad_csrf = admin_client.post(path, json=bad_payload)
                self.assertEqual(
                    res_bad_csrf.status_code, 403,
                    f"Endpoint {path} failed to reject invalid CSRF"
                )

                # C. Valid CSRF (via Header or Body) -> ACCEPTED (non-403)
                res_valid_header = admin_client.post(
                    path,
                    json=payload,
                    headers={"X-CSRF-Token": valid_csrf},
                )
                self.assertNotEqual(
                    res_valid_header.status_code, 403,
                    f"Endpoint {path} rejected valid CSRF header"
                )

    # =========================================================================
    # SEED IDEMPOTENCY & TEST ISOLATION
    # =========================================================================

    def test_seed_manager_consecutive_idempotency(self):
        """Verify SeedManager.run_all_seeds() can be executed multiple times without errors or duplicates."""
        seed_mgr = SeedManager(self.db_mgr)

        # Run 1: initial or repeat
        seed_mgr.run_all_seeds()

        # Run 2: consecutive execution against already-initialized database
        seed_mgr.run_all_seeds()

        # Run 3: ensure zero collisions
        seed_mgr.run_all_seeds()

        # Verify admin count for default admin is exactly 1
        conn = self.db_mgr.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM "Admins" WHERE username = %s', ("admin",))
        admin_count = cur.fetchone()[0]
        cur.close()
        self.assertEqual(admin_count, 1)

    # =========================================================================
    # POSTGRESQL TRANSACTION SAFETY & ERROR RECOVERY
    # =========================================================================

    def test_postgresql_aborted_transaction_auto_recovery(self):
        """
        Verify that when a SQL error aborts a transaction (status=3),
        subsequent queries recover cleanly via rollback instead of failing with
        'current transaction is aborted, commands ignored until end of transaction block'.
        """
        conn = self.db_mgr.get_connection()
        cur = conn.cursor()

        # 1. Intentionally trigger an invalid query
        try:
            cur.execute("SELECT * FROM non_existent_table_for_transaction_test_xyz;")
        except Exception:
            pass  # Expected syntax/relation error

        # 2. Next valid query MUST succeed without crashing from transaction-in-error state
        cur.execute("SELECT 1;")
        row = cur.fetchone()
        self.assertEqual(row[0], 1)
        cur.close()

    # =========================================================================
    # URL HASH UNIQUENESS & CONCURRENT UPSERT
    # =========================================================================

    def test_url_hash_uniqueness_on_conflict_upsert(self):
        """Verify ON CONFLICT (url_hash) updates existing row and keeps table unique."""
        import uuid
        test_url = f"https://example.com/unique-test-{uuid.uuid4()}"

        opp1 = Opportunity(title="Version 1", url=test_url, source_id="github_search", score=50)
        opp2 = Opportunity(title="Version 2 Updated", url=test_url, source_id="github_search", score=90)

        # First insert
        id1 = self.opp_repo.upsert(opp1)
        self.assertIsNotNone(id1)

        # Second insert with same canonical URL
        id2 = self.opp_repo.upsert(opp2)
        self.assertIsNotNone(id2)

        # Must resolve to the SAME canonical database record
        self.assertEqual(id1, id2)

        # Exactly 1 record exists
        conn = self.db_mgr.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*), title, score FROM "Opportunities" WHERE url_hash = %s GROUP BY title, score', (opp1.generate_url_hash(),))
        row = cur.fetchone()
        cur.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)
        self.assertEqual(row[1], "Version 2 Updated")
        self.assertEqual(row[2], 90)


if __name__ == "__main__":
    unittest.main()
