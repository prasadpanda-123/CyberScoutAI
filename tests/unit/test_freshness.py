"""
Unit tests for Freshness Analyzer (Phase 12 Feature 2).
"""

from datetime import datetime, timezone, timedelta
import unittest
from src.intelligence.production.freshness_analyzer import FreshnessAnalyzer


class TestFreshness(unittest.TestCase):
    def setUp(self):
        self.analyzer = FreshnessAnalyzer(max_days_old=90, archive_after_days=60)

    def test_fresh_item(self):
        now_str = datetime.now(timezone.utc).isoformat()
        score, days_old, days_rem, label, expired = self.analyzer.analyze_freshness(published_date_str=now_str)
        self.assertEqual(score, 100.0)
        self.assertEqual(days_old, 0)
        self.assertEqual(label, "Fresh")
        self.assertFalse(expired)

    def test_expired_item(self):
        old_dt = (datetime.now(timezone.utc) - timedelta(days=70)).isoformat()
        score, days_old, days_rem, label, expired = self.analyzer.analyze_freshness(published_date_str=old_dt)
        self.assertTrue(expired)
        self.assertEqual(label, "Expired")


if __name__ == "__main__":
    unittest.main()
