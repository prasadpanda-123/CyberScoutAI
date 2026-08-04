"""
Unit tests for Historical Analyzer (Phase 12 Feature 6).
"""

import unittest
from src.intelligence.production.historical_analyzer import HistoricalLifecycleAnalyzer
from src.models.opportunity import Opportunity


class TestHistoricalTracking(unittest.TestCase):
    def setUp(self):
        self.analyzer = HistoricalLifecycleAnalyzer()

    def test_record_change_entry(self):
        rec = self.analyzer.record_change("opp-123", "STATUS_CHANGE", "active", "expired")
        self.assertEqual(rec["opportunity_id"], "opp-123")
        self.assertEqual(rec["old_value"], "active")
        self.assertEqual(rec["new_value"], "expired")

    def test_analyze_lifecycle_delta(self):
        opp1 = Opportunity(id="opp-1", title="Test", url="https://example.com", source_id="s", status="active", score=50)
        opp2 = Opportunity(id="opp-1", title="Test", url="https://example.com", source_id="s", status="expired", score=80)
        changes = self.analyzer.analyze_lifecycle_delta(opp1, opp2)
        self.assertEqual(len(changes), 2)
        change_types = [c["change_type"] for c in changes]
        self.assertIn("STATUS_CHANGE", change_types)
        self.assertIn("SCORE_CHANGE", change_types)


if __name__ == "__main__":
    unittest.main()
