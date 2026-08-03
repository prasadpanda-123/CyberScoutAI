"""
Unit tests for QueryBuilder Phase 2 dynamic query generation.
"""

import unittest

from src.intelligence.query_builder import QueryBuilder


class TestQueryBuilderPhase2(unittest.TestCase):
    def setUp(self):
        self.builder = QueryBuilder()

    def test_generate_queries_for_category(self):
        queries = self.builder.generate_queries(category="internship", max_queries=10)
        self.assertIsInstance(queries, list)
        self.assertGreater(len(queries), 0)
        self.assertLessEqual(len(queries), 10)
        first_q = queries[0]
        self.assertEqual(first_q.category, "internship")
        self.assertNotIn("{keyword}", first_q.query_text)

    def test_generate_queries_without_synonyms(self):
        queries_with = self.builder.generate_queries(category="internship", include_synonyms=True, max_queries=100)
        queries_without = self.builder.generate_queries(category="internship", include_synonyms=False, max_queries=100)
        self.assertGreaterEqual(len(queries_with), len(queries_without))


if __name__ == "__main__":
    unittest.main()
