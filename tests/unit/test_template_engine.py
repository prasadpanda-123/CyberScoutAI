"""
Unit tests for SearchTemplateEngine (Phase 2).
"""

import unittest

from src.intelligence.template_engine import SearchTemplateEngine


class TestSearchTemplateEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SearchTemplateEngine()

    def test_get_templates_for_category(self):
        templates = self.engine.get_templates_for_category("internship")
        self.assertIsInstance(templates, list)
        self.assertGreater(len(templates), 0)
        self.assertEqual(templates[0].category, "internship")

    def test_render_queries(self):
        rendered = self.engine.render_queries("SOC", category="internship")
        self.assertIsInstance(rendered, list)
        self.assertGreater(len(rendered), 0)
        self.assertIn("SOC internship", rendered)


if __name__ == "__main__":
    unittest.main()
