"""
Unit tests for Database Repositories (Phase 1.2).
"""

from pathlib import Path
import tempfile
import unittest

from src.database.connection import DatabaseManager
from src.database.history_repository import EmailHistoryRepository, SearchHistoryRepository
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.models.enums import OpportunityCategory, Status
from src.models.opportunity import Opportunity


class TestRepositories(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_repo.db"
        self.db_manager = DatabaseManager(db_path=self.db_path)
        self.db_manager.initialize_database()

        self.opp_repo = OpportunityRepository(self.db_manager)
        self.source_repo = SourceRepository(self.db_manager)
        self.search_repo = SearchHistoryRepository(self.db_manager)
        self.email_repo = EmailHistoryRepository(self.db_manager)

        # Seed default source to fulfill Foreign Key constraints
        self.source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": "sans",
                        "name": "SANS Institute",
                        "collection_method": "html",
                        "default_category": "scholarship",
                    },
                    {
                        "id": "github_sec",
                        "name": "GitHub Security Repos",
                        "collection_method": "api",
                        "default_category": "github_repository",
                    },
                ]
            }
        )

    def tearDown(self):
        self.db_manager.close()
        self.temp_dir.cleanup()

    def test_opportunity_repository_crud_and_upsert(self):
        # 1. Insert Canonical Opportunity
        canonical_opp = Opportunity(
            id="canonical-123",
            title="Canonical SANS FastTrack",
            url="https://cyberfasttrack.org/canonical",
            source_id="sans",
            category=OpportunityCategory.SCHOLARSHIP.value,
            score=95,
        )
        self.opp_repo.upsert(canonical_opp)

        # 2. Insert Duplicate Candidate Opportunity
        opp = Opportunity(
            title="SANS CyberFastTrack 2026",
            url="https://cyberfasttrack.org",
            source_id="sans",
            category=OpportunityCategory.SCHOLARSHIP.value,
            score=90,
        )

        opp_id = self.opp_repo.upsert(opp)
        self.assertEqual(opp_id, opp.id)

        # 3. Get by ID
        fetched = self.opp_repo.get_by_id(opp_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "SANS CyberFastTrack 2026")
        self.assertEqual(fetched.score, 90)

        # 4. Get Active Opportunities
        active_list = self.opp_repo.get_active_opportunities()
        self.assertGreaterEqual(len(active_list), 2)

        # 5. Update Status & Mark Duplicate
        self.opp_repo.mark_as_duplicate(opp_id, canonical_id=canonical_opp.id)
        fetched_dup = self.opp_repo.get_by_id(opp_id)
        self.assertEqual(fetched_dup.status, Status.DUPLICATE.value)
        self.assertEqual(fetched_dup.duplicate_of_id, canonical_opp.id)

    def test_source_repository_sync(self):
        active_sources = self.source_repo.get_active_sources()
        self.assertGreaterEqual(len(active_sources), 2)

    def test_history_repositories(self):
        import uuid
        # Test SearchHistory
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        self.search_repo.start_run(run_id, sources_run=["github_sec"])
        self.search_repo.complete_run(run_id, status="success", items_collected=10)

        # Test EmailHistory with a valid Opportunity record
        opp_id = f"opp-test-{uuid.uuid4().hex[:8]}"
        opp = Opportunity(
            id=opp_id,
            title="Test Opp for Email",
            url=f"https://example.com/test-{opp_id}",
            source_id="sans",
        )
        self.opp_repo.upsert(opp)

        self.assertFalse(self.email_repo.is_already_emailed(opp.id))
        self.email_repo.record_emailed_opportunity(opp.id, email_run_id=f"email-run-{opp_id}")
        self.assertTrue(self.email_repo.is_already_emailed(opp.id))


if __name__ == "__main__":
    unittest.main()
