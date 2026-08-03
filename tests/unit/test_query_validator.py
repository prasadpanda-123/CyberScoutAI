"""
Unit tests for QueryValidator (Phase 2).
"""

import unittest

from src.intelligence.planner_models import SearchPlan, SearchTask
from src.intelligence.query_validator import QueryValidator
from src.models.search_models import SearchQuery


class TestQueryValidator(unittest.TestCase):
    def setUp(self):
        self.validator = QueryValidator()

    def test_validate_valid_query(self):
        sq = SearchQuery(query_text="SOC internship remote", keywords=["SOC"])
        result = self.validator.validate_query(sq)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_unrendered_template_query(self):
        sq = SearchQuery(query_text="{keyword} internship", keywords=["soc"])
        result = self.validator.validate_query(sq)
        self.assertFalse(result.is_valid)
        self.assertIn("Unrendered template variable", result.errors[0])

    def test_validate_empty_plan(self):
        plan = SearchPlan(tasks=[])
        result = self.validator.validate_plan(plan)
        self.assertFalse(result.is_valid)
        self.assertIn("zero tasks", result.errors[0])

    def test_validate_valid_plan(self):
        task = SearchTask(
            source_id="github_search",
            query_text="soc tool",
            target_url="https://api.github.com/search/repositories?q=soc+tool",
            category="github_repository",
            collection_method="api",
        )
        plan = SearchPlan(tasks=[task])
        result = self.validator.validate_plan(plan)
        self.assertTrue(result.is_valid)


if __name__ == "__main__":
    unittest.main()
