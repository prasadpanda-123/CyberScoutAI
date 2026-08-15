"""
Phase 4 Unit Tests: URL Normalization, Opportunity Deduplication, Date Extraction & Categorization.

Verifies:
1. Centralized URL Normalization (canonical hostname, trailing slash, fragments, tracking params).
2. Pre-Insert Opportunity Deduplication and Field Merging.
3. Database Duplicate Group Cleanup and Deterministic Survivor Selection.
4. Contextual Release Date and Application Deadline Extraction.
5. Opportunity Categorization against canonical OpportunityCategory enums.
"""

import time
import unittest
from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity
from src.models.source import Source
from src.processors.classifier import ClassifierProcessor
from src.processors.date_parser import extract_dates_from_text, parse_and_format_date
from src.processors.normalizer import NormalizerProcessor
from src.utils.url_utils import normalize_url


class TestPhase4DeduplicationAndIntelligence(unittest.TestCase):
    def setUp(self):
        self.classifier = ClassifierProcessor()
        self.normalizer = NormalizerProcessor()
        self.db_manager = None
        self.opp_repo = None
        self.source_repo = None
        self.test_source_id = "src_nvd"

    def _ensure_db(self):
        if self.db_manager is None:
            self.db_manager = DatabaseManager()
            self.db_manager.initialize_database()
            self.opp_repo = OpportunityRepository(self.db_manager)
            self.source_repo = SourceRepository(self.db_manager)
            test_src = Source(
                id="test_source_p4",
                name="Test Source",
                collection_method="rss",
                default_category="other",
                status="active",
                enabled=True,
                official=True,
                trust_score=100.0,
                maintenance_level="high",
                update_frequency="daily",
                max_requests_per_run=10,
                request_delay_ms=100,
            )
            try:
                self.source_repo.save_source(test_src)
                self.test_source_id = test_src.id
            except Exception:
                pass

    def test_url_normalization_canonical_rules(self):
        """Verify URL normalization canonicalization rules."""
        # 1. Hostname case & trailing slash
        self.assertEqual(
            normalize_url("https://EXAMPLE.COM/ctf/"),
            "https://example.com/ctf"
        )
        # 2. www prefix stripping
        self.assertEqual(
            normalize_url("https://www.example.com/bounty"),
            "https://example.com/bounty"
        )
        # 3. Fragment removal
        self.assertEqual(
            normalize_url("https://example.com/opp#section1"),
            "https://example.com/opp"
        )
        # 4. Tracking parameter stripping while keeping resource ID
        self.assertEqual(
            normalize_url("https://example.com/item?utm_source=google&id=12345&fbclid=XYZ"),
            "https://example.com/item?id=12345"
        )
        # 5. Default port removal
        self.assertEqual(
            normalize_url("https://example.com:443/page"),
            "https://example.com/page"
        )

    def test_pre_insert_deduplication_and_merging(self):
        """Verify pre-insert duplicate detection merges fields into existing survivor record."""
        self._ensure_db()
        ts_id = int(time.time() * 1000)
        base_url = f"https://example.com/opportunity_{ts_id}"

        # Item A: has title and description, but no deadline
        opp_a = Opportunity(
            title=f"Security Internship {ts_id}",
            url=base_url,
            source_id=self.test_source_id,
            description="Cybersecurity Summer Internship Program 2026",
            deadline=None,
            score=50,
        )
        saved_id_a, is_dup_a = self.opp_repo.save_opportunity_with_deduplication(opp_a)
        self.assertFalse(is_dup_a)

        # Item B: same destination URL with tracking param, includes deadline
        opp_b = Opportunity(
            title=f"Security Internship {ts_id}",
            url=f"{base_url}?utm_source=email#overview",
            source_id=self.test_source_id,
            description="Cybersecurity Summer Internship Program 2026",
            deadline="2026-08-31",
            score=80,
        )
        saved_id_b, is_dup_b = self.opp_repo.save_opportunity_with_deduplication(opp_b)
        self.assertTrue(is_dup_b)
        self.assertEqual(saved_id_a, saved_id_b)

        # Verify merged survivor record in DB
        survivor = self.opp_repo.get_by_id(saved_id_a)
        self.assertIsNotNone(survivor)
        self.assertEqual(str(survivor.deadline), "2026-08-31")
        self.assertEqual(survivor.score, 80)

    def test_database_duplicate_cleanup(self):
        """Verify database duplicate cleanup groups duplicates and marks redundant records."""
        self._ensure_db()
        ts_id = int(time.time() * 1000)
        target_url = f"https://example.com/cleanup_dup_{ts_id}"

        # Insert 2 duplicate records directly
        opp1 = Opportunity(
            title=f"CTF Challenge {ts_id}",
            url=target_url,
            source_id=self.test_source_id,
            description="Description 1",
            deadline="2026-09-15",
            score=60,
        )
        opp2 = Opportunity(
            title=f"CTF Challenge {ts_id}",
            url=f"{target_url}/",
            source_id=self.test_source_id,
            description="Description 2",
            published_date="2026-08-01",
            score=40,
        )
        self.opp_repo.upsert(opp1)
        self.opp_repo.upsert(opp2)

        # Run database duplicate cleanup
        stats = self.opp_repo.cleanup_database_duplicates()
        self.assertGreaterEqual(stats.get("duplicate_groups_found", 0), 1)

        # Verify survivor record has merged dates
        survivor = self.opp_repo.get_by_id(opp1.id)
        self.assertIsNotNone(survivor)
        self.assertEqual(str(survivor.deadline), "2026-09-15")
        self.assertEqual(str(survivor.published_date), "2026-08-01")

        # Verify secondary record is marked duplicate
        dup_rec = self.opp_repo.get_by_id(opp2.id)
        self.assertEqual(dup_rec.status, Status.DUPLICATE.value)

    def test_contextual_date_extraction(self):
        """Verify release date and deadline extraction from contextual text."""
        # 1. Textual deadline
        text1 = "CyberScout Hackathon 2026. Application Deadline: August 31, 2026. Join now!"
        dates1 = extract_dates_from_text(text1)
        self.assertEqual(dates1["deadline"], "2026-08-31")

        # 2. Textual published date
        text2 = "Security Advisory. Published: 2026-08-15. Details follow."
        dates2 = extract_dates_from_text(text2)
        self.assertEqual(dates2["published_date"], "2026-08-15")

        # 3. Copyright year must NOT be extracted as deadline
        text3 = "CyberScout Intelligence Platform. Copyright © 2026. All rights reserved."
        dates3 = extract_dates_from_text(text3)
        self.assertIsNone(dates3["deadline"])

    def test_opportunity_categorization(self):
        """Verify categorization maps items to canonical OpportunityCategory enum values."""
        # Internship
        opp_intern = Opportunity(
            title="Offensive Security Internship 2026",
            url="https://example.com/intern1",
            source_id=self.test_source_id,
            category="other",
        )
        classified_intern = self.classifier.process(opp_intern)
        self.assertEqual(classified_intern.category, OpportunityCategory.INTERNSHIP.value)

        # CTF
        opp_ctf = Opportunity(
            title="Global Capture The Flag Jeopardy CTF",
            url="https://example.com/ctf1",
            source_id=self.test_source_id,
            category="other",
        )
        classified_ctf = self.classifier.process(opp_ctf)
        self.assertEqual(classified_ctf.category, OpportunityCategory.CTF.value)

        # Hackathon
        opp_hack = Opportunity(
            title="Cybersecurity Student Hackathon 2026",
            url="https://example.com/hack1",
            source_id=self.test_source_id,
            category="other",
        )
        classified_hack = self.classifier.process(opp_hack)
        self.assertEqual(classified_hack.category, OpportunityCategory.HACKATHON.value)


if __name__ == "__main__":
    unittest.main()
