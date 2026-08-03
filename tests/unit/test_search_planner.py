"""
Unit tests for SearchPlanner (Phase 2).
"""

import unittest

from src.intelligence.search_planner import SearchPlanner


class TestSearchPlanner(unittest.TestCase):
    def setUp(self):
        self.planner = SearchPlanner()

    def test_create_search_plan(self):
        plan = self.planner.create_search_plan(categories=["internship", "ctf"], max_queries_per_category=5)
        self.assertIsNotNone(plan)
        self.assertGreater(plan.total_tasks, 0)
        self.assertIsInstance(plan.sources_targeted, list)
        self.assertGreater(len(plan.sources_targeted), 0)

        # Check first task structure
        first_task = plan.tasks[0]
        self.assertIsNotNone(first_task.source_id)
        self.assertIsNotNone(first_task.query_text)
        self.assertIsNotNone(first_task.target_url)
        self.assertNotIn("{keyword}", first_task.query_text)

    def test_get_tasks_for_source(self):
        plan = self.planner.create_search_plan(categories=["ctf"], max_queries_per_category=5)
        ctf_tasks = plan.get_tasks_for_source("ctftime")
        self.assertIsInstance(ctf_tasks, list)
        self.assertGreater(len(ctf_tasks), 0)


if __name__ == "__main__":
    unittest.main()
