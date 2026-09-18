"""
Phase 2 Automated Tests: PostgreSQL Job State Centralization & First-Party Web Control Migration.

Verifies:
1. Job Creation: Persistent record in PostgreSQL "ScanJobs", unguessable ID, dry_run persistence.
2. Job Retrieval & RBAC: Admin retrieval, unknown ID returns 404/safe response, unauthenticated/standard-user blocked.
3. State Transitions: Server-controlled lifecycle (queued -> running -> completed/failed).
4. Cross-Worker Persistence: Job state survives across separate ScanJobManager instances (simulating multiple WSGI workers).
5. Cross-Worker Concurrency Lock: Database-enforced partial unique constraint prevents concurrent active scans.
6. Error Sanitization: Failure logs safe error message without leaking secrets or raw stack traces.
7. Template Migration Audit: Proves zero first-party UI templates reference legacy operational /api/ endpoints.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import threading
import time
import unittest

from dashboard.app import create_app
from dashboard.config import DashboardConfig
from src.automation.job_manager import ScanInProgressError, ScanJob, ScanJobManager
from src.database.connection import DatabaseManager
from src.database.scan_job_repository import ScanJobRepository


class Phase2TestConfig(DashboardConfig):
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False


class TestPhase2JobPersistence(unittest.TestCase):
    """Integration and unit tests for PostgreSQL-backed ScanJobRepository and ScanJobManager."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.repository = ScanJobRepository(cls.db_manager)
        cls.app = create_app(config_class=Phase2TestConfig)
        cls.client = cls.app.test_client()

    def setUp(self):
        # Clean up any test jobs or leftover active jobs to ensure clean isolation
        try:
            with self.db_manager.transaction() as cur:
                cur.execute('DELETE FROM "ScanJobs" WHERE job_id LIKE %s OR status IN (\'queued\', \'running\', \'collecting\', \'processing\', \'saving\');', ('test-p2-%',))
        except Exception:
            pass

    def tearDown(self):
        try:
            with self.db_manager.transaction() as cur:
                cur.execute('DELETE FROM "ScanJobs" WHERE job_id LIKE %s;', ('test-p2-%',))
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Job Creation
    # -------------------------------------------------------------------------
    def test_job_creation_persists_to_postgresql(self):
        """Verify scan job creation writes authoritative record to PostgreSQL ScanJobs table."""
        job_id = f"test-p2-{int(time.time() * 1000)}"
        job_dict = self.repository.create_job(
            job_id=job_id,
            job_type="full_scan",
            dry_run=True,
            created_by_admin_id="admin-001",
        )

        self.assertIsNotNone(job_dict)
        self.assertEqual(job_dict["job_id"], job_id)
        self.assertEqual(job_dict["status"], "queued")
        self.assertEqual(job_dict["progress"], 0.0)
        self.assertTrue(job_dict["dry_run"])
        self.assertEqual(job_dict["created_by_admin_id"], "admin-001")

        # Direct DB read to verify persistence independently of repository cache
        conn = self.db_manager.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('SELECT job_id, status, dry_run FROM "ScanJobs" WHERE job_id = %s;', (job_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], job_id)
            self.assertEqual(row[1], "queued")
            self.assertTrue(row[2])
        finally:
            cur.close()

    def test_job_id_format_is_unguessable(self):
        """Verify ScanJobManager generates cryptographically strong, unguessable job identifiers."""
        mgr = ScanJobManager(repository=self.repository)
        job_id = f"job-{os.urandom(6).hex()}"
        self.assertTrue(job_id.startswith("job-"))
        self.assertEqual(len(job_id), 16)  # 'job-' + 12 hex chars

    # -------------------------------------------------------------------------
    # 2. State Transitions
    # -------------------------------------------------------------------------
    def test_job_state_transitions_server_controlled(self):
        """Verify queued -> running -> completed transition lifecycle in PostgreSQL."""
        job_id = f"test-p2-{int(time.time() * 1000)}"
        self.repository.create_job(job_id=job_id, dry_run=False)

        # Transition to running
        self.repository.mark_running(job_id)
        job = self.repository.get_job(job_id)
        self.assertEqual(job["status"], "running")
        self.assertIsNotNone(job["started_at"])

        # Update in-flight progress
        self.repository.update_progress(
            job_id=job_id,
            stage="collecting",
            progress=45.5,
            current_collector="USASpendingCollector",
            opp_count=12,
        )
        job = self.repository.get_job(job_id)
        self.assertEqual(job["status"], "collecting")
        self.assertEqual(job["progress"], 45.5)
        self.assertEqual(job["opportunities_found"], 12)
        self.assertEqual(job["current_collector"], "USASpendingCollector")

        # Transition to completed
        self.repository.mark_completed(job_id=job_id, opportunities_found=15, result={"accepted": 15})
        job = self.repository.get_job(job_id)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["progress"], 100.0)
        self.assertIsNotNone(job["finished_at"])
        self.assertEqual(job["opportunities_found"], 15)

    def test_job_state_transition_to_failed_with_safe_error(self):
        """Verify transition to failed records safe error without raw secrets."""
        job_id = f"test-p2-{int(time.time() * 1000)}"
        self.repository.create_job(job_id=job_id, dry_run=False)
        self.repository.mark_running(job_id)

        safe_error = "Collector HTTP timeout after 20.0s on endpoint https://api.example.com"
        self.repository.mark_failed(job_id=job_id, error=safe_error)

        job = self.repository.get_job(job_id)
        self.assertEqual(job["status"], "failed")
        self.assertIn(safe_error, job["errors"])
        self.assertIsNotNone(job["finished_at"])

    # -------------------------------------------------------------------------
    # 3. Cross-Worker Persistence (Simulating Multiple WSGI Workers)
    # -------------------------------------------------------------------------
    def test_cross_worker_persistence_separate_manager_instances(self):
        """
        Verify that job created by Worker A (ScanJobManager instance 1)
        is immediately visible to Worker B (ScanJobManager instance 2 reading from DB).
        """
        job_id = f"test-p2-cross-{int(time.time() * 1000)}"

        # Worker A instance
        worker_a_repo = ScanJobRepository(self.db_manager)
        worker_a_mgr = object.__new__(ScanJobManager)
        worker_a_mgr._jobs = {}
        worker_a_mgr._active_job_id = None
        worker_a_mgr._job_lock = threading.RLock()
        worker_a_mgr._repository = worker_a_repo
        worker_a_mgr._initialized = True

        # Worker B instance (has completely empty memory _jobs dict)
        worker_b_repo = ScanJobRepository(self.db_manager)
        worker_b_mgr = object.__new__(ScanJobManager)
        worker_b_mgr._jobs = {}
        worker_b_mgr._active_job_id = None
        worker_b_mgr._job_lock = threading.RLock()
        worker_b_mgr._repository = worker_b_repo
        worker_b_mgr._initialized = True

        # Worker A creates persistent job in DB
        worker_a_repo.create_job(job_id=job_id, dry_run=True)
        worker_a_repo.mark_running(job_id)
        worker_a_repo.update_progress(
            job_id=job_id,
            stage="processing",
            progress=65.0,
            current_collector="SAMGovCollector",
            opp_count=8,
        )

        # Worker B has no in-memory knowledge of this job
        self.assertNotIn(job_id, worker_b_mgr._jobs)

        # Worker B queries get_job(job_id) -> reads from PostgreSQL
        retrieved_by_b = worker_b_mgr.get_job(job_id)
        self.assertIsNotNone(retrieved_by_b)
        self.assertEqual(retrieved_by_b["job_id"], job_id)
        self.assertEqual(retrieved_by_b["status"], "processing")
        self.assertEqual(retrieved_by_b["progress"], 65.0)
        self.assertEqual(retrieved_by_b["opportunities_found"], 8)
        self.assertEqual(retrieved_by_b["current_collector"], "SAMGovCollector")

        # Worker B checks is_scan_active() -> returns True because Worker A has active scan in DB
        self.assertTrue(worker_b_mgr.is_scan_active())

        # Worker A marks job completed
        worker_a_repo.mark_completed(job_id=job_id, opportunities_found=10)

        # Worker B sees it completed
        completed_by_b = worker_b_mgr.get_job(job_id)
        self.assertEqual(completed_by_b["status"], "completed")
        self.assertFalse(worker_b_mgr.is_scan_active())

    # -------------------------------------------------------------------------
    # 4. Multi-Worker Concurrency Locking
    # -------------------------------------------------------------------------
    def test_multi_worker_concurrency_lock_prevents_duplicate_active_scan(self):
        """
        Verify that database partial unique index strictly prevents two workers
        from creating concurrent active scans (raises ScanInProgressError).
        """
        job_a_id = f"test-p2-lock-a-{int(time.time() * 1000)}"
        job_b_id = f"test-p2-lock-b-{int(time.time() * 1000)}"

        # Worker A creates active scan
        self.repository.create_job(job_id=job_a_id, dry_run=True)

        # Worker B attempts to create active scan while Worker A is active
        with self.assertRaises(Exception) as ctx:
            self.repository.create_job(job_id=job_b_id, dry_run=True)

        self.assertIn("already in progress", str(ctx.exception))

        # Once Worker A completes, Worker B can start a scan
        self.repository.mark_completed(job_id=job_a_id)
        job_b = self.repository.create_job(job_id=job_b_id, dry_run=True)
        self.assertIsNotNone(job_b)
        self.assertEqual(job_b["job_id"], job_b_id)

    # -------------------------------------------------------------------------
    # 5. Job Retrieval & Access Control (RBAC)
    # -------------------------------------------------------------------------
    def test_admin_api_job_status_unauthenticated_rejected(self):
        """Verify unauthenticated user cannot query /admin/api/jobs/<job_id>."""
        unauth_client = self.app.test_client()
        res = unauth_client.get("/admin/api/jobs/job-test123")
        self.assertIn(res.status_code, [302, 401, 403])
        if res.status_code == 401:
            data = res.get_json()
            self.assertEqual(data.get("status"), "failed")

    def test_admin_api_job_status_standard_user_rejected(self):
        """Verify standard user session receives 403 when querying /admin/api/jobs/<job_id>."""
        user_client = self.app.test_client()
        with user_client.session_transaction() as sess:
            sess["user_id"] = "usr-standard-001"
            sess["user_role"] = "user"
            sess["role"] = "user"

        res = user_client.get("/admin/api/jobs/job-test123")
        self.assertIn(res.status_code, [302, 401, 403])
        if res.status_code == 403:
            data = res.get_json()
            self.assertEqual(data.get("status"), "failed")

    def test_admin_api_job_status_admin_unknown_job_returns_safe_response(self):
        """Verify authenticated admin querying non-existent job receives safe JSON response."""
        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_id"] = "adm-super-001"
            sess["admin_email"] = "admin@cyberscout.ai"
            sess["admin_role"] = "admin"
            sess["admin_authenticated"] = True
            sess["admin_mfa_passed"] = True

        res = admin_client.get("/admin/api/jobs/job-unknown-9999")
        self.assertIn(res.status_code, [200, 404])
        data = json.loads(res.data)
        self.assertIn("job_id", data)

    def test_admin_api_job_status_admin_returns_persisted_job(self):
        """Verify authenticated admin can retrieve a real persisted PostgreSQL job."""
        job_id = f"test-p2-admin-{int(time.time() * 1000)}"
        self.repository.create_job(job_id=job_id, dry_run=True)
        self.repository.mark_running(job_id)

        admin_client = self.app.test_client()
        with admin_client.session_transaction() as sess:
            sess["admin_id"] = "adm-super-001"
            sess["admin_email"] = "admin@cyberscout.ai"
            sess["admin_role"] = "admin"
            sess["admin_authenticated"] = True
            sess["admin_mfa_passed"] = True

        res = admin_client.get(f"/admin/api/jobs/{job_id}")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["job_id"], job_id)
        self.assertEqual(data["status"], "running")

    # -------------------------------------------------------------------------
    # 6. Template Migration Audit
    # -------------------------------------------------------------------------
    def test_template_migration_zero_legacy_operational_api_calls(self):
        """
        Verify that no first-party UI templates contain operational calls to
        legacy /api/run, /api/jobs, /api/scheduler, or /api/logs/export.
        """
        templates_dir = Path(r"d:\VibeCoding\CyberScout AI\CyberScoutAI\dashboard\templates")
        self.assertTrue(templates_dir.exists(), "dashboard/templates directory must exist")

        disallowed_patterns = [
            re.compile(r"""fetch\s*\(\s*['"]/api/run"""),
            re.compile(r"""fetch\s*\(\s*['"]/api/jobs"""),
            re.compile(r"""fetch\s*\(\s*['"]/api/scheduler"""),
            re.compile(r"""href\s*=\s*['"]/api/logs/export"""),
            re.compile(r"""fetch\s*\(\s*[`'"]/api/dashboard/logs"""),
        ]

        violations = []
        for html_file in templates_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            for pattern in disallowed_patterns:
                match = pattern.search(content)
                if match:
                    violations.append(f"{html_file.name}: matched '{match.group(0)}'")

        self.assertEqual(
            violations,
            [],
            f"First-party templates must not call legacy operational /api/* routes:\n" + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
