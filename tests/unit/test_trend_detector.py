"""
Unit tests for Trend Detector (Phase 12 Feature 7).
"""

import unittest
from src.intelligence.production.trend_detector import TrendDetector
from src.models.opportunity import Opportunity


class TestTrendDetector(unittest.TestCase):
    def setUp(self):
        self.detector = TrendDetector()

    def test_trend_detection_summary(self):
        opps = [
            Opportunity(title="Opp 1", url="https://example.com/1", source_id="s1", category="internship", provider="OWASP", tags=["python", "security"]),
            Opportunity(title="Opp 2", url="https://example.com/2", source_id="s2", category="internship", provider="OWASP", tags=["python", "pentest"]),
        ]
        trends = self.detector.analyze_trends(opps)
        self.assertEqual(trends["total_analyzed"], 2)
        self.assertIn("python", trends["top_skills"])
        self.assertEqual(trends["top_skills"]["python"], 2)
        self.assertIn("OWASP", trends["top_providers"])


if __name__ == "__main__":
    unittest.main()
