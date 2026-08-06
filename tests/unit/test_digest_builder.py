"""
Unit tests for Notifier Digest Builder (Phase 7).
"""

from pathlib import Path
import unittest

from src.database.connection import DatabaseManager
from src.database.opportunity_repository import OpportunityRepository
from src.database.source_repository import SourceRepository
from src.models.opportunity import Opportunity
from src.notifier.digest_builder import DigestBuilder


class TestDigestBuilder(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_path=Path(":memory:"))
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
        opp = Opportunity(
            title="SANS CyberFastTrack 2026",
            url="https://example.com/sans",
            source_id="sans",
            category="scholarship",
            score=95,
        )
        opp_repo.upsert(opp)

    def tearDown(self):
        self.db_manager.close()

    def test_build_digest(self):
        builder = DigestBuilder(db_manager=self.db_manager)
        digest = builder.build_digest()

        self.assertGreaterEqual(digest.total_opportunities, 1)
        self.assertIn("scholarship", digest.categories)
        self.assertGreaterEqual(digest.stats["average_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
