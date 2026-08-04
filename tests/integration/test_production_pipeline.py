"""
Integration tests for Phase 12 Production Intelligence Pipeline.
"""

from pathlib import Path
import unittest

from src.automation.pipeline import PipelineRunner
from src.database.connection import DatabaseManager
from src.intelligence.production.production_engine import ProductionEngine
from src.models.opportunity import Opportunity


class TestProductionPipeline(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager(db_path=Path(":memory:"))
        self.db_manager.initialize_database()
        self.engine = ProductionEngine()

    def tearDown(self):
        self.db_manager.close()

    def test_production_engine_pipeline_eval(self):
        opps = [
            Opportunity(
                title="OWASP Security Research Internship",
                url="https://example.com/owasp-internship",
                source_id="owasp_feed",
                description="Comprehensive web security internship learning OWASP Top 10 vulnerabilities.",
                provider="OWASP",
                category="internship",
                confidence_score=95.0,
                quality_score=90.0,
            ),
            Opportunity(
                title="IPTV Channels List 2026",
                url="https://example.com/iptv-list",
                source_id="generic_rss",
                description="Free IPTV playlists M3U streams.",
                is_rejected=True,
                rejection_reason="PLAYLIST_DETECTED",
            ),
        ]

        evaluated = self.engine.evaluate_batch(opps)
        accepted = [o for o in evaluated if not o.is_rejected]

        self.assertEqual(len(evaluated), 2)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].title, "OWASP Security Research Internship")
        self.assertEqual(accepted[0].link_status, "VALID")
        self.assertGreaterEqual(accepted[0].freshness_score, 90.0)


if __name__ == "__main__":
    unittest.main()
