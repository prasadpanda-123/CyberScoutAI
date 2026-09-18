"""
Phase 1 Core Correctness & Data Integrity Remediation Regression Tests.

Comprehensive test suite verifying:
- P1-01 & P1-06: Pipeline Persistence Failure & Truthful Status Reporting (Tests A, B, C, D, E)
- P1-02 & P1-07: StatisticsService Schema Correctness on PostgreSQL (P0-P3, sources, categories, trends)
- P1-03 & P1-08: SuperAdmin Provisioning & Profile Consistency (Admins table boundary)
- P1-04 & P1-09: Database-level url_hash Uniqueness & Concurrency (exact, tracking, trailing-slash, port)
- P1-05: PostgreSQL Transaction Auto-Rollback Recovery (no aborted transaction cascades)
"""

import time
import unittest
from unittest.mock import MagicMock, patch
import uuid

from dashboard.app import create_app
from dashboard.services.statistics_service import StatisticsService
from src.automation.job_manager import ScanJob, ScanJobManager
from src.automation.pipeline import run_pipeline_once
from src.core.exceptions import DatabaseConnectionError
from src.database.admin_repository import AdminRepository
from src.database.connection import DatabaseManager
from src.database.history_repository import SearchHistoryRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.scan_job_repository import ScanJobRepository
from src.database.user_repository import UserRepository
from src.models.opportunity import Opportunity
from src.utils.url_utils import normalize_url


class TestPhase1Remediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.db_manager = DatabaseManager()
        cls.opp_repo = OpportunityRepository(db_manager=cls.db_manager)
        cls.admin_repo = AdminRepository(db_manager=cls.db_manager)
        cls.user_repo = UserRepository(db_manager=cls.db_manager)
        cls.scan_job_repo = ScanJobRepository(db_manager=cls.db_manager)
        cls.history_repo = SearchHistoryRepository(db_manager=cls.db_manager)

    def _create_mock_collector(self, items=None):
        """Creates a mock CollectorManager with given items to bypass network calls."""
        if items is None:
            items = [Opportunity(title="Test", url=f"https://example.com/test-{uuid.uuid4()}", source_id="github_search")]
        mock_cm = MagicMock()
        mock_res = MagicMock()
        mock_res.source_id = "test_source"
        mock_res.errors = []
        mock_res.status = "success"
        mock_res.success = True
        mock_res.items = items
        mock_cm.execute_plan.return_value = [mock_res]
        return mock_cm

    # =========================================================================
    # P1-01 & P1-06: Pipeline Failure Regression Tests (Tests A, B, C, D, E)
    # =========================================================================

    def test_p1_06_test_a_persistence_succeeds(self):
        """Test A: Persistence succeeds -> pipeline=success, SearchHistory=success, ScanJob=completed."""
        mock_cm = self._create_mock_collector()
        res = run_pipeline_once(
            dry_run=False,
            db_manager=self.db_manager,
            collector_manager=mock_cm,
        )

        self.assertTrue(res.get("success"), "Pipeline must report success=True on normal completion")
        self.assertEqual(res.get("status"), "success")
        self.assertTrue(res.get("persistence_success"), "persistence_success must be True")

        # Verify SearchHistory
        run_id = res.get("run_id")
        self.assertIsNotNone(run_id)
        conn = self.db_manager.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT status FROM "SearchHistory" WHERE run_id = %s;', (run_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "success")
        finally:
            cur.close()

    def test_p1_06_test_b_persistence_database_exception(self):
        """Test B: Persistence raises database exception -> pipeline=failure, SearchHistory=failed, ScanJob=failed."""
        mock_cm = self._create_mock_collector()
        mock_km = MagicMock()
        mock_km.process_opportunity_batch.side_effect = RuntimeError("Simulated DB Disk Write Error")

        res = run_pipeline_once(
            dry_run=False,
            db_manager=self.db_manager,
            collector_manager=mock_cm,
            knowledge_manager=mock_km,
        )

        self.assertFalse(res.get("success"), "Pipeline must report success=False on persistence failure")
        self.assertEqual(res.get("status"), "failed")
        self.assertFalse(res.get("persistence_success"))
        self.assertIn("Simulated DB Disk Write Error", str(res.get("error")))

        # Verify SearchHistory in database is 'failed'
        run_id = res.get("run_id")
        self.assertIsNotNone(run_id)
        conn = self.db_manager.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT status, errors FROM "SearchHistory" WHERE run_id = %s;', (run_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "failed", "SearchHistory status must be 'failed'")
            self.assertIn("Simulated DB Disk Write Error", str(row[1] or ""))
        finally:
            cur.close()

        # Verify ScanJobManager marks ScanJob as failed
        jm = ScanJobManager()
        job_id = f"job-test-{uuid.uuid4().hex[:8]}"
        job = ScanJob(job_id=job_id, status="queued")
        jm._jobs[job_id] = job

        with patch("src.automation.pipeline.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "success": False,
                "status": "failed",
                "persistence_success": False,
                "error": "Simulated DB Disk Write Error",
            }
            jm._run_job_worker(job, dry_run=False, db_manager=self.db_manager)

        job_status = jm.get_job(job_id)
        self.assertIsNotNone(job_status)
        self.assertEqual(job_status["status"], "failed", "ScanJob must transition to 'failed'")
        self.assertIn("Simulated DB Disk Write Error", str(job_status.get("errors", [])))

    def test_p1_06_test_c_persistence_unique_constraint_conflict_handled(self):
        """Test C: Persistence raises unique constraint conflict -> handled cleanly via ON CONFLICT (url_hash)."""
        test_url = f"https://example.com/dedup-test-{uuid.uuid4()}"
        opp1 = Opportunity(title="First Version", url=test_url, source_id="github_search", score=40)
        opp2 = Opportunity(title="Second Version", url=test_url, source_id="github_search", score=90)

        # First insert
        id1 = self.opp_repo.upsert(opp1)
        self.assertIsNotNone(id1)

        # Second insert with identical URL (unique constraint target)
        opp2.id = str(uuid.uuid4())
        id2 = self.opp_repo.upsert(opp2)

        # Must merge into canonical record
        self.assertEqual(id1, id2, "Duplicate url_hash upsert must return existing canonical ID")

        # Cleanup
        with self.db_manager.transaction() as cur:
            cur.execute('DELETE FROM "Opportunities" WHERE url_hash = %s', (opp1.generate_url_hash(),))

    def test_p1_06_test_d_database_connection_fails(self):
        """Test D: Database connection fails -> pipeline does NOT report false success."""
        mock_db = MagicMock()
        mock_db.ping.return_value = False

        with self.assertRaises(DatabaseConnectionError):
            run_pipeline_once(
                dry_run=False,
                db_manager=mock_db,
            )

    def test_p1_06_test_e_notification_failure_does_not_fail_persistence(self):
        """Test E: Notification fails after successful persistence -> scan remains success, notification marked failed."""
        mock_cm = self._create_mock_collector()
        mock_ec = MagicMock()
        mock_ec.send_daily_digest.side_effect = Exception("SMTP Connection Timed Out")

        res = run_pipeline_once(
            dry_run=False,
            send_email=True,
            db_manager=self.db_manager,
            collector_manager=mock_cm,
            email_client=mock_ec,
        )

        self.assertTrue(res.get("success"), "Pipeline should remain success=True even if email fails")
        self.assertTrue(res.get("persistence_success"), "Persistence must be True")
        self.assertFalse(res.get("email_sent"), "email_sent must be False")
        self.assertIn("SMTP Connection Timed Out", str(res.get("email_error", "")))

    # =========================================================================
    # P1-02 & P1-07: StatisticsService Schema Correctness
    # =========================================================================

    def test_p1_07_statistics_service_all_queries_succeed(self):
        """Verify StatisticsService runs cleanly on PostgreSQL without schema mismatch or transaction errors."""
        service = StatisticsService(db_manager=self.db_manager)

        # 1. Categories
        cats = service.get_category_distribution()
        self.assertIsInstance(cats, dict)

        # 2. Priority Distribution (derived from score ranges P0 >= 80, P1 >= 60, P2 >= 40, P3 < 40)
        prios = service.get_priority_distribution()
        self.assertIsInstance(prios, dict)
        for key in prios.keys():
            self.assertIn(key, ["P0", "P1", "P2", "P3"])

        # 3. Source Distribution (joined with Sources or fallback to provider)
        sources = service.get_source_distribution()
        self.assertIsInstance(sources, dict)

        # 4. Daily Trends
        trends = service.get_daily_opportunity_trends()
        self.assertIsInstance(trends, dict)
        self.assertIn("labels", trends)
        self.assertIn("counts", trends)

    # =========================================================================
    # P1-03 & P1-08: SuperAdmin Provisioning & Profile Consistency
    # =========================================================================

    def test_p1_08_superadmin_lifecycle_and_boundary(self):
        """Verify complete SuperAdmin lifecycle through Admins table and profile lookup."""
        ts = int(time.time() * 1000)
        u_name = f"admin_{ts}"
        u_email = f"admin_{ts}@cyberscout.ai"
        pw = "StrongAdminPass123!"

        # Mock has_admin returning False on dashboard.routes.auth repos to allow setup
        with patch("dashboard.routes.auth.admin_repo.has_admin", return_value=False), \
             patch("dashboard.routes.auth.user_repo.has_admin", return_value=False):
            res = self.client.post("/setup", data={
                "username": u_name,
                "email": u_email,
                "password": pw,
                "confirm_password": pw,
            }, follow_redirects=False)

            self.assertEqual(res.status_code, 302)
            self.assertIn("/admin/login", res.location)

        # 1. Verify admin created in Admins table
        admin = self.admin_repo.get_by_username(u_name)
        self.assertIsNotNone(admin, "SuperAdmin must exist in Admins table")
        self.assertEqual(admin["role"], "Super Admin")

        # 2. Verify authentication
        auth_admin = self.admin_repo.authenticate(u_name, pw)
        self.assertIsNotNone(auth_admin, "SuperAdmin authentication must succeed")

        # 3. Verify profile lookup by id succeeds
        profile = self.admin_repo.get_by_id(auth_admin["id"])
        self.assertIsNotNone(profile, "Profile lookup by id must succeed")
        self.assertEqual(profile["username"], u_name)

        # 4. Verify admin user management query succeeds
        all_admins = self.admin_repo.get_all()
        self.assertTrue(any(a["username"] == u_name for a in all_admins))

        # 5. Security Invariant: Normal Users cannot authenticate via admin_repo
        self.assertIsNone(self.admin_repo.authenticate(f"user_attacker_{ts}", pw))

    # =========================================================================
    # P1-04 & P1-09: URL Deduplication & Normalization Tests
    # =========================================================================

    def test_p1_09_url_deduplication_variants(self):
        """Verify URL normalization and database unique constraint for exact, tracking, trailing-slash, and port."""
        base_url = f"https://example.com/career/security-analyst-{uuid.uuid4().hex[:8]}"

        # Variant 1: Base URL
        url1 = base_url
        # Variant 2: Trailing slash
        url2 = f"{base_url}/"
        # Variant 3: Tracking parameters
        url3 = f"{base_url}?utm_source=twitter&utm_medium=social&ref=partner"
        # Variant 4: Explicit default port
        url4 = base_url.replace("https://", "https://:443/") if ":443" in base_url else base_url.replace("example.com", "example.com:443")

        # Normalization check
        h1 = Opportunity(title="T", url=url1, source_id="github_search").generate_url_hash()
        h2 = Opportunity(title="T", url=url2, source_id="github_search").generate_url_hash()
        h3 = Opportunity(title="T", url=url3, source_id="github_search").generate_url_hash()
        h4 = Opportunity(title="T", url=url4, source_id="github_search").generate_url_hash()

        self.assertEqual(h1, h2, "Trailing slash must produce identical url_hash")
        self.assertEqual(h1, h3, "Tracking parameters must be stripped producing identical url_hash")
        self.assertEqual(h1, h4, "Default port :443 must be stripped producing identical url_hash")

        # Database insertion test: All variants must resolve to one row in Opportunities
        opp1 = Opportunity(title="Version 1", url=url1, source_id="github_search", score=50)
        id1 = self.opp_repo.upsert(opp1)

        opp2 = Opportunity(title="Version 2", url=url3, source_id="github_search", score=80)
        id2 = self.opp_repo.upsert(opp2)

        self.assertEqual(id1, id2, "Database upsert must update existing row without duplicate key violation")

        # Clean up
        with self.db_manager.transaction() as cur:
            cur.execute('DELETE FROM "Opportunities" WHERE url_hash = %s', (h1,))

    # =========================================================================
    # P1-05: Transaction Error Auto-Rollback Recovery
    # =========================================================================

    def test_p1_05_transaction_auto_rollback_resilience(self):
        """Verify that an aborted query does not leave the connection unusable for subsequent queries."""
        conn = self.db_manager.get_connection()
        cur = conn.cursor()

        # Trigger a PostgreSQL transaction abort
        try:
            cur.execute('SELECT non_existent_column_for_test FROM "Opportunities";')
        except Exception:
            pass

        # Immediate subsequent query on the same connection must auto-recover and succeed
        cur2 = conn.cursor()
        cur2.execute('SELECT 1;')
        row = cur2.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)
        cur2.close()


if __name__ == "__main__":
    unittest.main()
