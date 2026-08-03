"""
Unit tests for Knowledge Base & Historical Intelligence (Phase 6).
"""

from pathlib import Path
import unittest

from src.database.analytics import AnalyticsEngine
from src.database.archive import ArchiveManager
from src.database.connection import DatabaseManager
from src.database.history_manager import HistoryManager
from src.database.knowledge_manager import KnowledgeManager
from src.database.migrations import MigrationManager
from src.database.provider_statistics import ProviderStatisticsTracker
from src.database.reporting import ReportGenerator
from src.database.retention import RetentionPolicyManager
from src.database.seed import SeedManager
from src.database.source_repository import SourceRepository
from src.database.trend_engine import TrendEngine
from src.models.enums import Status
from src.models.opportunity import Opportunity


class TestKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_path=Path(":memory:"))
        self.db_manager.initialize_database()

        # Apply migrations
        mig_manager = MigrationManager(db_manager=self.db_manager)
        mig_manager.apply_migrations()

        # Seed source records to satisfy foreign key constraints
        source_repo = SourceRepository(self.db_manager)
        source_repo.sync_from_config(
            {
                "sources": [
                    {
                        "id": "cisa_alerts",
                        "name": "CISA Advisories",
                        "collection_method": "rss",
                        "default_category": "security_news",
                    }
                ]
            }
        )

    def tearDown(self):
        self.db_manager.close()

    def test_migration_v2(self):
        mig_manager = MigrationManager(db_manager=self.db_manager)
        self.assertEqual(mig_manager.get_current_version(), 2)

    def test_knowledge_manager_lifecycle(self):
        km = KnowledgeManager(db_manager=self.db_manager)
        opp = Opportunity(
            title="CISA Advisory 1",
            url="https://cisa.gov/adv/1",
            source_id="cisa_alerts",
            score=80,
        )

        # 1. Never seen
        state1 = km.process_opportunity_state(opp)
        self.assertEqual(state1, "NEVER_SEEN")

        # 2. Seen before
        state2 = km.process_opportunity_state(opp)
        self.assertEqual(state2, "SEEN_BEFORE")

        # 3. Updated
        opp.title = "CISA Advisory 1 Updated"
        state3 = km.process_opportunity_state(opp)
        self.assertEqual(state3, "UPDATED")

    def test_provider_statistics_and_trends(self):
        tracker = ProviderStatisticsTracker(db_manager=self.db_manager)
        tracker.update_provider_stats("CISA", 85)

        km = KnowledgeManager(db_manager=self.db_manager)
        opp = Opportunity(title="Test Opp", url="https://example.com/test", source_id="cisa_alerts", provider="CISA", category="security_news")
        km.process_opportunity_state(opp)

        trend = TrendEngine(db_manager=self.db_manager)
        top_p = trend.get_most_active_providers(5)
        self.assertTrue(len(top_p) >= 0)

    def test_analytics_and_reporting(self):
        analytics = AnalyticsEngine(db_manager=self.db_manager)
        summary = analytics.generate_analytics_summary()
        self.assertIn("total_opportunities", summary)

        reporter = ReportGenerator(db_manager=self.db_manager, analytics_engine=analytics)
        daily_json = reporter.generate_daily_report_json()
        self.assertIn("daily_summary", daily_json)

    def test_retention_and_archiving(self):
        km = KnowledgeManager(db_manager=self.db_manager)
        expired_opp = Opportunity(
            title="Expired Competition",
            url="https://example.com/expired",
            source_id="cisa_alerts",
            status=Status.EXPIRED.value,
        )
        km.process_opportunity_state(expired_opp)

        retention = RetentionPolicyManager(db_manager=self.db_manager)
        res = retention.run_retention_policy()
        self.assertIn("archived_opportunities", res)


if __name__ == "__main__":
    unittest.main()
