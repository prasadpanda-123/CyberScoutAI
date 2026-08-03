"""
Unit tests for Opportunity Intelligence & Ranking Engine (Phase 5).
"""

import unittest

from src.models.enums import OpportunityCategory
from src.models.opportunity import Opportunity
from src.intelligence.deadline_engine import DeadlineEngine
from src.intelligence.duplicate_filter import DuplicateFilter
from src.intelligence.priority_engine import PriorityEngine
from src.intelligence.provider_engine import ProviderEngine
from src.intelligence.ranking_engine import RankingEngine
from src.intelligence.score_calculator import ScoreCalculator
from src.intelligence.weight_manager import WeightManager


class TestRankingEngine(unittest.TestCase):
    def test_provider_engine(self):
        engine = ProviderEngine()
        self.assertEqual(engine.get_provider_bonus("CISA"), 25)
        self.assertEqual(engine.get_provider_bonus("Google"), 20)
        self.assertEqual(engine.get_provider_bonus("UnknownProvider"), 0)

    def test_deadline_engine(self):
        engine = DeadlineEngine()
        status, days = engine.evaluate_deadline("2026-08-05T00:00:00Z")
        self.assertIn(status, ["URGENT", "UPCOMING", "EXPIRED", "LONG_TERM"])

    def test_priority_engine(self):
        engine = PriorityEngine()
        self.assertEqual(engine.assign_priority(90), "P0")
        self.assertEqual(engine.assign_priority(70), "P1")
        self.assertEqual(engine.assign_priority(50), "P2")
        self.assertEqual(engine.assign_priority(20), "P3")

    def test_ranking_engine_batch(self):
        engine = RankingEngine()
        items = [
            Opportunity(
                title="Free CISA Security Advisory & Certificate",
                url="https://cisa.gov/advisory/1",
                description="Free accredited security advisory with certificate.",
                provider="CISA",
                paid=False,
                certificate=True,
                remote=True,
                source_id="cisa",
                score=30,
            ),
            Opportunity(
                title="Paid Private Course",
                url="https://example.com/course",
                description="Paid course without certificate.",
                provider="Unknown",
                paid=True,
                certificate=False,
                source_id="test",
                score=10,
            ),
        ]
        ranked = engine.rank_batch(items)
        self.assertEqual(len(ranked), 2)
        self.assertGreater(ranked[0].score, ranked[1].score)
        self.assertEqual(ranked[0].raw_data["priority"], "P0")
        self.assertIn("recommendation_reason", ranked[0].raw_data)

    def test_duplicate_filter(self):
        dup_filter = DuplicateFilter()
        item1 = Opportunity(title="Opp 1", url="https://example.com/opp", source_id="test", score=50)
        item2 = Opportunity(title="Opp 1", url="https://example.com/opp", source_id="test", score=90)

        filtered = dup_filter.filter_duplicates([item1, item2])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].score, 90)


if __name__ == "__main__":
    unittest.main()
