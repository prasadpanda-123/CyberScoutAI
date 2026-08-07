"""
Unit tests for Notifier History tracking (Phase 7).
"""

from pathlib import Path
import unittest

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.models.opportunity import Opportunity
from src.notifier.history import HistoryTracker


class TestHistoryTracker(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager()
        self.db_manager.initialize_database()

        # Seed Source
        source_repo = SourceRepository(self.db_manager)
        source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": "sans",
                        "name": "SANS Institute",
                        "collection_method": "rss",
                        "default_category": "scholarship",
                    }
                ]
            }
        )

        # Seed Opportunity
        opp_repo = OpportunityRepository(self.db_manager)
        self.opp = Opportunity(
            id="opp-sans-123",
            title="SANS CyberFastTrack 2026",
            url="https://example.com/sans",
            source_id="sans",
            category="scholarship",
            score=95,
        )
        opp_repo.upsert(self.opp)

    def tearDown(self):
        self.db_manager.close()

    def test_log_delivery(self):
        tracker = HistoryTracker(db_manager=self.db_manager)
        tracker.log_delivery(self.opp.id, email_run_id="run-1")
        self.assertTrue(tracker.repo.is_already_emailed(self.opp.id))


if __name__ == "__main__":
    unittest.main()
