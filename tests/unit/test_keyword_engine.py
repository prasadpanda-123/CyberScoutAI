"""
Unit tests for KeywordEngine (Phase 2).
"""

import unittest

from src.intelligence.keyword_engine import KeywordEngine


class TestKeywordEngine(unittest.TestCase):
    def setUp(self):
        self.engine = KeywordEngine()

    def test_get_all_keywords(self):
        keywords = self.engine.get_all_keywords()
        self.assertIsInstance(keywords, list)
        self.assertGreater(len(keywords), 0)
        self.assertIn("soc", keywords)

    def test_get_keywords_by_category(self):
        cyber_keywords = self.engine.get_keywords_by_category("cybersecurity")
        self.assertIsInstance(cyber_keywords, list)
        self.assertIn("soc", cyber_keywords)

    def test_expand_keyword(self):
        expansions = self.engine.expand_keyword("soc")
        self.assertIsInstance(expansions, list)
        self.assertGreaterEqual(len(expansions), 1)
        self.assertEqual(expansions[0], "soc")
        self.assertIn("security operations center", expansions)

    def test_get_expanded_keywords(self):
        expanded = self.engine.get_expanded_keywords("cybersecurity")
        self.assertIsInstance(expanded, list)
        self.assertIn("soc", expanded)
        self.assertIn("security operations center", expanded)


if __name__ == "__main__":
    unittest.main()
