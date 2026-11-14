"""
Comprehensive Gate & Regression Test Suite for CyberScout AI Phase 1.1.

Validates:
- SEC-01: Open Redirect Defense across Login, MFA, and OTP Verification stages.
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

        # 2. POST credentials with malicious next parameter
        with patch("src.auth.admin_auth.AdminSecurityManager.generate_otp_code", return_value="654321"):
            post_res = self.client.post(
                "/admin/login",
                data={
                    "admin_username": uname,
                    "admin_password": pwd,
                    "next": evil_target,
                },
                follow_redirects=False,
            )
            self.assertEqual(post_res.status_code, 302)
            self.assertIn("/admin/verify-otp", post_res.location)

            with self.client.session_transaction() as sess:
                # Ensure stored next_url in session/mfa was sanitized to internal default
                stored_next = sess.get("admin_pending_next")
                if stored_next:
                    self.assertNotIn("attacker.example", stored_next)

            # 3. POST valid OTP to complete MFA
            otp_res = self.client.post(
                "/admin/verify-otp",
                data={
                    "otp_code": "654321",
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

        with patch("src.auth.admin_auth.AdminSecurityManager.generate_otp_code", return_value="112233"):
            post_res = self.client.post(
                "/admin/login",
                data={
                    "admin_username": uname,
                    "admin_password": pwd,
                    "next": safe_target,
                },
                follow_redirects=False,
            )
            self.assertEqual(post_res.status_code, 302)

            otp_res = self.client.post(
                "/admin/verify-otp",
                data={"otp_code": "112233"},
                follow_redirects=False,
            )
            self.assertEqual(otp_res.status_code, 302)
            self.assertEqual(otp_res.location, safe_target)

    # =========================================================================
    # =========================================================================


    # =========================================================================
    # =========================================================================


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
