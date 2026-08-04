"""
Unit tests for Duplicate Detection (Stage 8: Duplicate Detection).
"""

import unittest
from src.models.opportunity import Opportunity
from src.processors.deduplicator import DeduplicatorProcessor


class TestDuplicateDetection(unittest.TestCase):
    def setUp(self):
        self.deduplicator = DeduplicatorProcessor()

    def test_duplicate_url_hash_detection(self):
        opp1 = Opportunity(
            title="OWASP Security Internship 2026",
            url="https://example.com/owasp-internship-2026",
            source_id="test",
        )
        opp2 = Opportunity(
            title="OWASP Security Internship 2026",
            url="https://example.com/owasp-internship-2026",
            source_id="test",
        )
        res1 = self.deduplicator.process(opp1)
        res2 = self.deduplicator.process(opp2)
        self.assertIsNotNone(res1)
        self.assertIsNone(res2)

    def test_fuzzy_title_similarity_duplicate(self):
        opp1 = Opportunity(
            title="Cybersecurity Research Analyst Internship Summer 2026",
            url="https://example.com/internship-a",
            source_id="test",
        )
        opp2 = Opportunity(
            title="Cybersecurity Research Analyst Internship Summer 2026",
            url="https://example.com/internship-a",
            source_id="test",
        )
        res1 = self.deduplicator.process(opp1)
        res2 = self.deduplicator.process(opp2)
        self.assertIsNotNone(res1)
        self.assertIsNone(res2)


if __name__ == "__main__":
    unittest.main()
