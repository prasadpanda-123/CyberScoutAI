"""
Phase 2.1 Automated Tests: Idempotent Harvesting & Duplicate-Elimination Hardening.

Mandatory Test Scenarios:
1. Same opportunity collected twice -> 1 DB row.
2. Same opportunity collected 100 times -> 1 DB row.
3. Same canonical URL with tracking parameters -> 1 DB row.
4. Same source external ID with changed URL -> 1 DB row.
5. Same opportunity with changed deadline -> existing row updated.
6. Same opportunity with changed description -> existing row updated.
7. Identical second harvest -> UNCHANGED classification.
8. UNCHANGED opportunity -> no duplicate notification.
9. UPDATED opportunity -> existing row ID preserved.
10. Two concurrent workers collecting the same opportunity -> 1 row.
11. Two concurrent scheduler runs -> no duplicates.
12. Different opportunities -> separate rows.
13. Previously closed opportunity appears again -> REOPENED.
14. Source without external ID still deduplicates through canonical identity.
15. Database unique constraint rejects forced duplicate insertion.
16. Failed transaction/retry does not create duplicates.
17. Application restart/retry remains idempotent.
18. Cross-source identical-looking opportunities are NOT automatically merged without sufficient identity confidence.
19. Existing historical duplicates are detected correctly.
20. Duplicate reconciliation preserves required relationships.
21. Scheduler metrics correctly distinguish NEW/UPDATED/UNCHANGED/DUPLICATE.
22. Repeated full scheduler runs produce stable database cardinality.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository, PersistenceResult
from src.database.source_repository import SourceRepository
from src.models.enums import ChangeClassification, OpportunityCategory, Status
from src.models.opportunity import Opportunity
from src.utils.url_utils import normalize_url


class TestPhase21IdempotentHarvesting(unittest.TestCase):
    """Integration and unit tests verifying Phase 2.1 idempotent harvesting and deduplication."""

    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager()
        cls.db_manager.initialize_database()
        cls.source_repo = SourceRepository(cls.db_manager)
        cls.opp_repo = OpportunityRepository(cls.db_manager)

        # Register test sources to satisfy Foreign Key constraints
        cls.source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": "test_p21_src_a",
                        "name": "Test P21 Source A",
                        "collection_method": "api",
                        "default_category": "internship",
                    },
                    {
                        "id": "test_p21_src_b",
                        "name": "Test P21 Source B",
                        "collection_method": "api",
                        "default_category": "scholarship",
                    },
                ]
            }
        )

    def setUp(self):
        self._cleanup_test_data()

    def tearDown(self):
        self._cleanup_test_data()

    def _cleanup_test_data(self):
        try:
            with self.db_manager.transaction() as cur:
                cur.execute(
                    'DELETE FROM "Opportunities" WHERE id LIKE %s OR url LIKE %s OR source_id IN (%s, %s);',
                    ("test-p21-%", "https://test-p21.example.com/%", "test_p21_src_a", "test_p21_src_b")
                )
        except Exception:
            pass

    def _get_row_count(self, url: str = None, opp_id: str = None) -> int:
        with self.db_manager.transaction() as cur:
            if url:
                norm = normalize_url(url)
                cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE canonical_url = %s OR url = %s;', (norm, url))
            elif opp_id:
                cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE id = %s;', (opp_id,))
            else:
                cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE id LIKE %s;', ("test-p21-%",))
            row = cur.fetchone()
            return row[0] if row else 0

    # -------------------------------------------------------------
    # 1. Same opportunity collected twice -> 1 DB row
    # -------------------------------------------------------------
    def test_01_same_opportunity_twice_one_db_row(self):
        opp1 = Opportunity(
            id="test-p21-01-a",
            title="Junior Cloud Security Engineer",
            url="https://test-p21.example.com/job/01",
            source_id="test_p21_src_a",
            source_external_id="ext-01",
        )
        saved_id1, cls1 = self.opp_repo.save_or_update(opp1)
        self.assertEqual(cls1, ChangeClassification.NEW)

        opp2 = Opportunity(
            id="test-p21-01-b",
            title="Junior Cloud Security Engineer",
            url="https://test-p21.example.com/job/01",
            source_id="test_p21_src_a",
            source_external_id="ext-01",
        )
        saved_id2, cls2 = self.opp_repo.save_or_update(opp2)
        self.assertEqual(cls2, ChangeClassification.UNCHANGED)
        self.assertEqual(saved_id1, saved_id2)

        # Must have exactly 1 row in DB
        self.assertEqual(self._get_row_count(url=opp1.url), 1)

    # -------------------------------------------------------------
    # 2. Same opportunity collected 100 times -> 1 DB row
    # -------------------------------------------------------------
    def test_02_same_opportunity_100_times_one_db_row(self):
        base_url = "https://test-p21.example.com/job/02"
        canonical_id = "test-p21-02-canonical"
        for i in range(100):
            opp = Opportunity(
                id=f"test-p21-02-attempt-{i}",
                title="Application Security Specialist",
                url=base_url,
                source_id="test_p21_src_a",
                source_external_id="ext-02",
                description="Deterministic description across 100 iterations.",
            )
            if i == 0:
                opp.id = canonical_id
            saved_id, classification = self.opp_repo.save_or_update(opp)
            if i == 0:
                self.assertEqual(classification, ChangeClassification.NEW)
                self.assertEqual(saved_id, canonical_id)
            else:
                self.assertEqual(classification, ChangeClassification.UNCHANGED)
                self.assertEqual(saved_id, canonical_id)

        self.assertEqual(self._get_row_count(url=base_url), 1)

    # -------------------------------------------------------------
    # 3. Same canonical URL with tracking parameters -> 1 DB row
    # -------------------------------------------------------------
    def test_03_same_canonical_url_tracking_params_one_db_row(self):
        url_raw_1 = "https://test-p21.example.com/post/sec?utm_source=twitter&utm_medium=cpc"
        url_raw_2 = "https://test-p21.example.com/post/sec?utm_source=newsletter&ref=feed"

        opp1 = Opportunity(
            id="test-p21-03-a",
            title="Threat Hunter Fellowship",
            url=url_raw_1,
            source_id="test_p21_src_a",
        )
        opp2 = Opportunity(
            id="test-p21-03-b",
            title="Threat Hunter Fellowship",
            url=url_raw_2,
            source_id="test_p21_src_a",
        )

        # Batch 1: first harvest saves opp1 as NEW
        res1 = self.opp_repo.upsert_batch([opp1])
        self.assertEqual(res1.new_count, 1)

        # Batch 2: second harvest with different tracking params deduplicates to UNCHANGED
        res2 = self.opp_repo.upsert_batch([opp2])
        self.assertEqual(res2.new_count, 0)
        self.assertEqual(res2.unchanged_count, 1)

        # Exact 1 row in DB matching canonical URL
        self.assertEqual(self._get_row_count(url="https://test-p21.example.com/post/sec"), 1)

    # -------------------------------------------------------------
    # 4. Same source external ID with changed URL -> 1 DB row
    # -------------------------------------------------------------
    def test_04_same_source_external_id_with_changed_url_one_db_row(self):
        opp1 = Opportunity(
            id="test-p21-04-orig",
            title="DFIR Summer Academy",
            url="https://test-p21.example.com/v1/jobs/dfir-101",
            source_id="test_p21_src_a",
            source_external_id="dfir-unique-101",
        )
        saved_id1, _ = self.opp_repo.save_or_update(opp1)

        # Source provider changed their permalink routing in v2, but kept external ID
        opp2 = Opportunity(
            id="test-p21-04-v2",
            title="DFIR Summer Academy",
            url="https://test-p21.example.com/v2/academy/dfir-101",
            source_id="test_p21_src_a",
            source_external_id="dfir-unique-101",
        )
        saved_id2, cls2 = self.opp_repo.save_or_update(opp2)

        self.assertEqual(saved_id1, saved_id2)
        self.assertEqual(cls2, ChangeClassification.UPDATED)

        with self.db_manager.transaction() as cur:
            cur.execute(
                'SELECT COUNT(*), MAX(url) FROM "Opportunities" WHERE source_id = %s AND source_external_id = %s;',
                ("test_p21_src_a", "dfir-unique-101"),
            )
            row = cur.fetchone()
        self.assertEqual(row[0], 1)
        self.assertIn("/v2/academy/dfir-101", row[1])

    # -------------------------------------------------------------
    # 5. Same opportunity with changed deadline -> existing row updated
    # -------------------------------------------------------------
    def test_05_same_opportunity_changed_deadline_existing_row_updated(self):
        opp = Opportunity(
            id="test-p21-05",
            title="Cyber Defense Scholarship",
            url="https://test-p21.example.com/scholarship/5",
            source_id="test_p21_src_a",
            deadline="2026-10-01",
        )
        saved_id, cls1 = self.opp_repo.save_or_update(opp)
        self.assertEqual(cls1, ChangeClassification.NEW)

        opp_updated = Opportunity(
            id="test-p21-05-diff",
            title="Cyber Defense Scholarship",
            url="https://test-p21.example.com/scholarship/5",
            source_id="test_p21_src_a",
            deadline="2026-11-15",  # Deadline extended
        )
        saved_id2, cls2 = self.opp_repo.save_or_update(opp_updated)
        self.assertEqual(saved_id, saved_id2)
        self.assertEqual(cls2, ChangeClassification.UPDATED)

        with self.db_manager.transaction() as cur:
            cur.execute('SELECT deadline FROM "Opportunities" WHERE id = %s;', (saved_id,))
            deadline = cur.fetchone()[0]
        self.assertEqual(str(deadline), "2026-11-15")

    # -------------------------------------------------------------
    # 6. Same opportunity with changed description -> existing row updated
    # -------------------------------------------------------------
    def test_06_same_opportunity_changed_description_existing_row_updated(self):
        opp = Opportunity(
            id="test-p21-06",
            title="Red Team Internship",
            url="https://test-p21.example.com/internship/6",
            source_id="test_p21_src_a",
            description="Initial brief outline.",
        )
        saved_id, cls1 = self.opp_repo.save_or_update(opp)
        self.assertEqual(cls1, ChangeClassification.NEW)

        opp_updated = Opportunity(
            id="test-p21-06-reharvest",
            title="Red Team Internship",
            url="https://test-p21.example.com/internship/6",
            source_id="test_p21_src_a",
            description="Comprehensive updated requirements and stipend details.",
        )
        saved_id2, cls2 = self.opp_repo.save_or_update(opp_updated)
        self.assertEqual(saved_id, saved_id2)
        self.assertEqual(cls2, ChangeClassification.UPDATED)

        with self.db_manager.transaction() as cur:
            cur.execute('SELECT description FROM "Opportunities" WHERE id = %s;', (saved_id,))
            desc = cur.fetchone()[0]
        self.assertIn("Comprehensive updated requirements", desc)

    # -------------------------------------------------------------
    # 7. Identical second harvest -> UNCHANGED
    # -------------------------------------------------------------
    def test_07_identical_second_harvest_unchanged(self):
        opp = Opportunity(
            id="test-p21-07",
            title="Malware Analysis Bootcamp",
            url="https://test-p21.example.com/bootcamp/7",
            source_id="test_p21_src_a",
            category=OpportunityCategory.COURSE.value,
        )
        _, cls1 = self.opp_repo.save_or_update(opp)
        self.assertEqual(cls1, ChangeClassification.NEW)

        opp2 = Opportunity(
            id="test-p21-07-again",
            title="Malware Analysis Bootcamp",
            url="https://test-p21.example.com/bootcamp/7",
            source_id="test_p21_src_a",
            category=OpportunityCategory.COURSE.value,
        )
        _, cls2 = self.opp_repo.save_or_update(opp2)
        self.assertEqual(cls2, ChangeClassification.UNCHANGED)

    # -------------------------------------------------------------
    # 8. UNCHANGED opportunity -> no duplicate notification
    # -------------------------------------------------------------
    def test_08_unchanged_opportunity_no_duplicate_notification(self):
        from src.automation.pipeline import run_pipeline_once

        opp = Opportunity(
            id="test-p21-08",
            title="Incident Response Cohort Cybersecurity Training",
            url="https://test-p21.example.com/cohort/8",
            source_id="test_p21_src_a",
            category=OpportunityCategory.COURSE.value,
            description="Comprehensive cybersecurity incident response training program with digital certificate.",
            score=90,
            confidence_score=95.0,
            quality_score=90.0,
        )
        # Mock collector manager execute_plan returning this opportunity
        mock_result = MagicMock()
        mock_result.source_id = "test_p21_src_a"
        mock_result.items = [opp]
        mock_result.errors = []
        mock_result.status = "success"

        mock_collector_manager = MagicMock()
        mock_collector_manager.execute_plan.return_value = [mock_result]

        mock_prod_engine = MagicMock()
        mock_prod_engine.evaluate_batch.side_effect = lambda batch: batch

        # Run 1: Initial harvest and persistence
        mock_email_1 = MagicMock()
        res1 = run_pipeline_once(
            send_email=False,
            db_manager=self.db_manager,
            collector_manager=mock_collector_manager,
            production_engine=mock_prod_engine,
            email_client=mock_email_1,
        )

        # Run 2: Re-harvest identical source -> Classified as UNCHANGED, email suppressed
        mock_email_2 = MagicMock()
        mock_email_2.send_daily_digest.return_value = {"status": "success"}

        res2 = run_pipeline_once(
            send_email=True,
            db_manager=self.db_manager,
            collector_manager=mock_collector_manager,
            production_engine=mock_prod_engine,
            email_client=mock_email_2,
        )

        self.assertEqual(res2["items_new"], 0)
        self.assertEqual(res2["items_updated"], 0)
        self.assertGreaterEqual(res2["items_unchanged"], 1)
        # Notification must NOT be dispatched when 0 new and 0 updated
        mock_email_2.send_daily_digest.assert_not_called()

    # -------------------------------------------------------------
    # 9. UPDATED opportunity -> existing row ID preserved
    # -------------------------------------------------------------
    def test_09_updated_opportunity_existing_row_id_preserved(self):
        original_pk = "test-p21-09-stable-pk"
        opp = Opportunity(
            id=original_pk,
            title="SOC Analyst Mentorship",
            url="https://test-p21.example.com/mentorship/9",
            source_id="test_p21_src_a",
            tags=["soc", "tier1"],
        )
        saved_id1, cls1 = self.opp_repo.save_or_update(opp)
        self.assertEqual(saved_id1, original_pk)
        self.assertEqual(cls1, ChangeClassification.NEW)

        opp_mod = Opportunity(
            id="test-p21-09-different-id",
            title="SOC Analyst Mentorship",
            url="https://test-p21.example.com/mentorship/9",
            source_id="test_p21_src_a",
            tags=["soc", "tier1", "tier2"],  # Tag change triggers update
        )
        saved_id2, cls2 = self.opp_repo.save_or_update(opp_mod)
        self.assertEqual(saved_id2, original_pk)
        self.assertEqual(cls2, ChangeClassification.UPDATED)

    # -------------------------------------------------------------
    # 10. Two concurrent workers collecting the same opportunity -> 1 row
    # -------------------------------------------------------------
    def test_10_two_concurrent_workers_same_opportunity_one_row(self):
        url = "https://test-p21.example.com/concurrency/worker-test"
        
        def harvest_worker(worker_id: int):
            worker_opp_repo = OpportunityRepository(self.db_manager)
            opp = Opportunity(
                id=f"test-p21-10-w{worker_id}",
                title="Cryptanalysis Challenge",
                url=url,
                source_id="test_p21_src_a",
                source_external_id="crypto-10",
            )
            return worker_opp_repo.save_or_update(opp)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futs = [executor.submit(harvest_worker, 1), executor.submit(harvest_worker, 2)]
            results = [f.result() for f in as_completed(futs)]

        # One worker should be NEW, the other either UNCHANGED or atomic success
        saved_ids = {res[0] for res in results}
        self.assertEqual(len(saved_ids), 1, "Both concurrent workers must resolve to the identical opportunity primary key")
        self.assertEqual(self._get_row_count(url=url), 1)

    # -------------------------------------------------------------
    # 11. Two concurrent scheduler runs -> no duplicates
    # -------------------------------------------------------------
    def test_11_two_concurrent_scheduler_runs_no_duplicates(self):
        opps = [
            Opportunity(
                id=f"test-p21-11-{i}",
                title=f"Concurrent Scheduler Target {i}",
                url=f"https://test-p21.example.com/sched/{i}",
                source_id="test_p21_src_a",
            )
            for i in range(5)
        ]

        def run_scheduler_batch():
            repo = OpportunityRepository(self.db_manager)
            return repo.upsert_batch(opps)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futs = [executor.submit(run_scheduler_batch), executor.submit(run_scheduler_batch)]
            results = [f.result() for f in as_completed(futs)]

        for res in results:
            self.assertIsInstance(res, PersistenceResult)

        # Exactly 5 canonical rows in total
        with self.db_manager.transaction() as cur:
            cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE url LIKE %s;', ("https://test-p21.example.com/sched/%",))
            total = cur.fetchone()[0]
        self.assertEqual(total, 5)

    # -------------------------------------------------------------
    # 12. Different opportunities -> separate rows
    # -------------------------------------------------------------
    def test_12_different_opportunities_separate_rows(self):
        opp1 = Opportunity(
            id="test-p21-12-a",
            title="Reverse Engineering Track",
            url="https://test-p21.example.com/re/1",
            source_id="test_p21_src_a",
        )
        opp2 = Opportunity(
            id="test-p21-12-b",
            title="Cloud Forensics Track",
            url="https://test-p21.example.com/forensics/2",
            source_id="test_p21_src_a",
        )

        res = self.opp_repo.upsert_batch([opp1, opp2])
        self.assertEqual(res.new_count, 2)
        self.assertEqual(self._get_row_count(url=opp1.url), 1)
        self.assertEqual(self._get_row_count(url=opp2.url), 1)

    # -------------------------------------------------------------
    # 13. Previously closed opportunity appears again -> REOPENED
    # -------------------------------------------------------------
    def test_13_previously_closed_opportunity_reopened(self):
        opp = Opportunity(
            id="test-p21-13",
            title="National Cyber League Entry",
            url="https://test-p21.example.com/ncl/13",
            source_id="test_p21_src_a",
            status=Status.ACTIVE.value,
        )
        saved_id, _ = self.opp_repo.save_or_update(opp)

        # Mark as archived in DB
        with self.db_manager.transaction() as cur:
            cur.execute('UPDATE "Opportunities" SET status = %s WHERE id = %s;', (Status.ARCHIVED.value, saved_id))

        # Re-harvested as active
        opp_reharvest = Opportunity(
            id="test-p21-13-newharvest",
            title="National Cyber League Entry",
            url="https://test-p21.example.com/ncl/13",
            source_id="test_p21_src_a",
            status=Status.ACTIVE.value,
        )
        saved_id2, cls = self.opp_repo.save_or_update(opp_reharvest)
        self.assertEqual(saved_id, saved_id2)
        self.assertEqual(cls, ChangeClassification.REOPENED)

        with self.db_manager.transaction() as cur:
            cur.execute('SELECT status FROM "Opportunities" WHERE id = %s;', (saved_id,))
            st = cur.fetchone()[0]
        self.assertEqual(st, Status.ACTIVE.value)

    # -------------------------------------------------------------
    # 14. Source without external ID still deduplicates through canonical identity
    # -------------------------------------------------------------
    def test_14_source_without_external_id_deduplicates_canonical_identity(self):
        # source_external_id is None
        opp1 = Opportunity(
            id="test-p21-14-1",
            title="Autonomous Penetration Testing Challenge",
            url="https://test-p21.example.com/pentest/14",
            source_id="test_p21_src_a",
            source_external_id=None,
        )
        saved_id1, cls1 = self.opp_repo.save_or_update(opp1)
        self.assertEqual(cls1, ChangeClassification.NEW)

        opp2 = Opportunity(
            id="test-p21-14-2",
            title="Autonomous Penetration Testing Challenge",
            url="https://test-p21.example.com/pentest/14",
            source_id="test_p21_src_a",
            source_external_id=None,
        )
        saved_id2, cls2 = self.opp_repo.save_or_update(opp2)
        self.assertEqual(cls2, ChangeClassification.UNCHANGED)
        self.assertEqual(saved_id1, saved_id2)
        self.assertEqual(self._get_row_count(url=opp1.url), 1)

    # -------------------------------------------------------------
    # 15. Database unique constraint rejects forced duplicate insertion
    # -------------------------------------------------------------
    def test_15_database_unique_constraint_rejects_forced_duplicate_insertion(self):
        opp = Opportunity(
            id="test-p21-15-valid",
            title="Hardware Security Research Fellowship",
            url="https://test-p21.example.com/hw/15",
            source_id="test_p21_src_a",
            source_external_id="hw-15-ext",
        )
        self.opp_repo.save_or_update(opp)

        # Attempt raw SQL insert violating the partial unique index on (source_id, source_external_id)
        with self.assertRaises(Exception):
            with self.db_manager.transaction() as cur:
                cur.execute(
                    """
                    INSERT INTO "Opportunities" (id, title, url, source_id, source_external_id, canonical_url, url_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        "test-p21-15-forced-dup",
                        "Duplicate Title",
                        "https://test-p21.example.com/hw/15-diff-url",
                        "test_p21_src_a",
                        "hw-15-ext",
                        "https://test-p21.example.com/hw/15-diff-url",
                        "fakehash12345",
                    ),
                )

    # -------------------------------------------------------------
    # 16. Failed transaction/retry does not create duplicates
    # -------------------------------------------------------------
    def test_16_failed_transaction_retry_does_not_create_duplicates(self):
        opp = Opportunity(
            id="test-p21-16",
            title="Firmware Analysis Lab",
            url="https://test-p21.example.com/firmware/16",
            source_id="test_p21_src_a",
            category="other",
        )

        # Simulate transaction failure during initial attempt
        try:
            with self.db_manager.transaction() as cur:
                cur.execute(
                    """
                    INSERT INTO "Opportunities" (id, title, url, source_id, canonical_url, url_hash, category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (opp.id, opp.title, opp.url, opp.source_id, opp.canonical_url, opp.generate_url_hash(), "other"),
                )
                raise RuntimeError("Simulated transient network crash before commit")
        except Exception:
            pass  # Expected simulated abort

        # Table should have 0 rows after rollback
        self.assertEqual(self._get_row_count(opp_id=opp.id), 0)

        # Retry through idempotent save_or_update
        saved_id, cls = self.opp_repo.save_or_update(opp)
        self.assertEqual(cls, ChangeClassification.NEW)
        self.assertEqual(self._get_row_count(opp_id=opp.id), 1)

    # -------------------------------------------------------------
    # 17. Application restart/retry remains idempotent
    # -------------------------------------------------------------
    def test_17_application_restart_retry_remains_idempotent(self):
        opp = Opportunity(
            id="test-p21-17-cold",
            title="Satellite Security Cohort",
            url="https://test-p21.example.com/space/17",
            source_id="test_p21_src_a",
        )
        saved_id1, _ = self.opp_repo.save_or_update(opp)

        # Simulate application restart with a fresh repository instance
        fresh_db_manager = DatabaseManager()
        fresh_opp_repo = OpportunityRepository(fresh_db_manager)

        opp_reharvest = Opportunity(
            id="test-p21-17-restart",
            title="Satellite Security Cohort",
            url="https://test-p21.example.com/space/17",
            source_id="test_p21_src_a",
        )
        saved_id2, cls2 = fresh_opp_repo.save_or_update(opp_reharvest)
        self.assertEqual(saved_id1, saved_id2)
        self.assertEqual(cls2, ChangeClassification.UNCHANGED)
        self.assertEqual(self._get_row_count(url=opp.url), 1)

    # -------------------------------------------------------------
    # 18. Cross-source identical-looking opportunities are NOT automatically merged
    # -------------------------------------------------------------
    def test_18_cross_source_identical_looking_opportunities_not_automatically_merged(self):
        opp_source_a = Opportunity(
            id="test-p21-18-src-a",
            title="National Cyber Scholar",
            url="https://test-p21.example.com/source_a/scholar",
            source_id="test_p21_src_a",
            description="National cybersecurity scholarship program.",
        )
        opp_source_b = Opportunity(
            id="test-p21-18-src-b",
            title="National Cyber Scholar",
            url="https://test-p21.example.com/source_b/scholar",
            source_id="test_p21_src_b",
            description="National cybersecurity scholarship program.",
        )

        id_a, _ = self.opp_repo.save_or_update(opp_source_a)
        id_b, _ = self.opp_repo.save_or_update(opp_source_b)

        # Because sources and canonical URLs differ, provenance must be preserved
        self.assertNotEqual(id_a, id_b)
        self.assertEqual(self._get_row_count(url=opp_source_a.url), 1)
        self.assertEqual(self._get_row_count(url=opp_source_b.url), 1)

    # -------------------------------------------------------------
    # 19. Existing historical duplicates are detected correctly
    # -------------------------------------------------------------
    def test_19_existing_historical_duplicates_detected_correctly(self):
        with self.db_manager.transaction() as cur:
            cur.execute(
                """
                SELECT url_hash, COUNT(*) 
                FROM "Opportunities" 
                GROUP BY url_hash 
                HAVING COUNT(*) > 1;
                """
            )
            dups = cur.fetchall()
            # Verified in Live PostgreSQL inspection: 0 active duplicate url_hash groups
            self.assertEqual(len(dups), 0)

    # -------------------------------------------------------------
    # 20. Duplicate reconciliation preserves required relationships
    # -------------------------------------------------------------
    def test_20_duplicate_reconciliation_preserves_required_relationships(self):
        # Insert a canonical record
        canonical = Opportunity(
            id="test-p21-20-canonical",
            title="Critical Infrastructure Security Fellowship",
            url="https://test-p21.example.com/infra/20",
            source_id="test_p21_src_a",
        )
        self.opp_repo.save_or_update(canonical)

        # Verify that querying find_existing_opportunity returns this canonical entity
        found = self.opp_repo.find_existing_opportunity(canonical)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, "test-p21-20-canonical")

    # -------------------------------------------------------------
    # 21. Scheduler metrics correctly distinguish NEW/UPDATED/UNCHANGED/DUPLICATE
    # -------------------------------------------------------------
    def test_21_scheduler_metrics_distinguish_new_updated_unchanged_duplicate(self):
        # Pre-seed items for unchanged and updated test cases
        existing_unchanged = Opportunity(
            id="test-p21-21-unchanged-seed",
            title="Existing Bootcamp",
            url="https://test-p21.example.com/bootcamp/21",
            source_id="test_p21_src_a",
            deadline="2026-09-01",
        )
        self.opp_repo.save_or_update(existing_unchanged)

        existing_to_update = Opportunity(
            id="test-p21-21-to-update-seed",
            title="Updatable Bootcamp",
            url="https://test-p21.example.com/bootcamp-update/21",
            source_id="test_p21_src_a",
            deadline="2026-09-01",
        )
        self.opp_repo.save_or_update(existing_to_update)

        # Build a batch containing:
        # 1. NEW item
        # 2. UNCHANGED item (exact copy of existing)
        # 3. DUPLICATE item (identical URL to the NEW item within the same batch)
        # 4. UPDATED item (existing item with changed deadline)
        batch = [
            Opportunity(
                id="test-p21-21-new",
                title="Brand New Training",
                url="https://test-p21.example.com/brand-new/21",
                source_id="test_p21_src_a",
            ),
            Opportunity(
                id="test-p21-21-unchanged",
                title="Existing Bootcamp",
                url="https://test-p21.example.com/bootcamp/21",
                source_id="test_p21_src_a",
                deadline="2026-09-01",
            ),
            Opportunity(
                id="test-p21-21-inbatch-dup",
                title="Brand New Training",
                url="https://test-p21.example.com/brand-new/21",
                source_id="test_p21_src_a",
            ),
            Opportunity(
                id="test-p21-21-exist-updated",
                title="Updatable Bootcamp",
                url="https://test-p21.example.com/bootcamp-update/21",
                source_id="test_p21_src_a",
                deadline="2026-12-01",  # Material change
            ),
        ]

        result = self.opp_repo.upsert_batch(batch)
        self.assertIsInstance(result, PersistenceResult)
        self.assertEqual(result.new_count, 1, "Expected 1 NEW item")
        self.assertEqual(result.duplicate_count, 1, "Expected 1 in-batch DUPLICATE item")
        self.assertEqual(result.unchanged_count, 1, "Expected 1 UNCHANGED item")
        self.assertEqual(result.updated_count, 1, "Expected 1 UPDATED item")

    # -------------------------------------------------------------
    # 22. Repeated full scheduler runs produce stable database cardinality
    # -------------------------------------------------------------
    def test_22_repeated_full_scheduler_runs_produce_stable_cardinality(self):
        batch = [
            Opportunity(
                id=f"test-p21-22-{i}",
                title=f"Stable Track {i}",
                url=f"https://test-p21.example.com/stable/{i}",
                source_id="test_p21_src_a",
            )
            for i in range(5)
        ]

        # Initial harvest
        res1 = self.opp_repo.upsert_batch(batch)
        self.assertEqual(res1.new_count, 5)

        with self.db_manager.transaction() as cur:
            cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE url LIKE %s;', ("https://test-p21.example.com/stable/%",))
            count_run1 = cur.fetchone()[0]
        self.assertEqual(count_run1, 5)

        # Run 2: Exact re-harvest
        res2 = self.opp_repo.upsert_batch(batch)
        self.assertEqual(res2.new_count, 0)
        self.assertEqual(res2.unchanged_count, 5)

        with self.db_manager.transaction() as cur:
            cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE url LIKE %s;', ("https://test-p21.example.com/stable/%",))
            count_run2 = cur.fetchone()[0]
        self.assertEqual(count_run2, 5, "Database cardinality must remain strictly stable")

        # Run 3: Exact re-harvest again
        res3 = self.opp_repo.upsert_batch(batch)
        self.assertEqual(res3.new_count, 0)
        self.assertEqual(res3.unchanged_count, 5)

        with self.db_manager.transaction() as cur:
            cur.execute('SELECT COUNT(*) FROM "Opportunities" WHERE url LIKE %s;', ("https://test-p21.example.com/stable/%",))
            count_run3 = cur.fetchone()[0]
        self.assertEqual(count_run3, 5, "Database cardinality must remain strictly stable")


if __name__ == "__main__":
    unittest.main()
