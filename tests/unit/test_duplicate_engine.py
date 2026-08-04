"""
Unit tests for Semantic Duplicate Engine (Phase 12 Feature 5).
"""

import unittest
from src.intelligence.production.duplicate_engine import SemanticDuplicateEngine
from src.models.opportunity import Opportunity


class TestDuplicateEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SemanticDuplicateEngine(similarity_threshold=0.8)

    def test_semantic_duplicate_merging(self):
        opp1 = Opportunity(
            title="Google Summer of Code Security Internship 2026",
            url="https://example.com/gsoc-1",
            source_id="test",
        )
        opp2 = Opportunity(
            title="Google Summer of Code Security Internship 2027",
            url="https://example.com/gsoc-2",
            source_id="test",
        )
        unique, merged = self.engine.process_batch([opp1, opp2])
        self.assertEqual(len(unique), 1)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].status, "duplicate")


if __name__ == "__main__":
    unittest.main()
