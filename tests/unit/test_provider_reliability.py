"""
Unit tests for Provider Reliability Engine (Phase 12 Feature 1).
"""

import unittest
from src.intelligence.production.provider_reliability import ProviderReliabilityEngine


class TestProviderReliability(unittest.TestCase):
    def setUp(self):
        self.engine = ProviderReliabilityEngine()

    def test_default_provider_scores(self):
        cisa_stats = self.engine.get_or_create_stats("cisa_alerts")
        self.assertEqual(cisa_stats.reliability_score, 100.0)
        self.assertEqual(cisa_stats.star_rating, "★★★★★")

    def test_record_successful_requests(self):
        pstats = self.engine.record_request_outcome("cisa_alerts", success=True, response_time=0.2)
        self.assertEqual(pstats.successful_requests, 1)
        self.assertEqual(pstats.consecutive_failures, 0)
        self.assertGreaterEqual(pstats.reliability_score, 90.0)

    def test_record_failures_decreases_score(self):
        for _ in range(5):
            self.engine.record_request_outcome("generic_rss", success=False, is_dns=True)
        pstats = self.engine.get_or_create_stats("generic_rss")
        self.assertLess(pstats.reliability_score, 40.0)
        self.assertEqual(pstats.consecutive_failures, 5)


if __name__ == "__main__":
    unittest.main()
