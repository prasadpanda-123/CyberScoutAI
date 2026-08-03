"""
Unit tests for SourceRegistry (Phase 2).
"""

import unittest

from src.intelligence.source_registry import SourceRegistry


class TestSourceRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = SourceRegistry()

    def test_get_all_sources(self):
        sources = self.registry.get_all_sources()
        self.assertIsInstance(sources, list)
        self.assertGreater(len(sources), 0)

    def test_get_source_by_id(self):
        source = self.registry.get_source("github_search")
        self.assertIsNotNone(source)
        self.assertEqual(source["name"], "GitHub Search API")
        self.assertTrue(source["supports_search"])

    def test_get_sources_for_category(self):
        ctf_sources = self.registry.get_sources_for_category("ctf")
        self.assertIsInstance(ctf_sources, list)
        self.assertGreater(len(ctf_sources), 0)
        source_ids = [s["id"] for s in ctf_sources]
        self.assertIn("ctftime", source_ids)

    def test_get_sources_by_capability(self):
        rss_sources = self.registry.get_sources_by_capability("supports_rss")
        self.assertIsInstance(rss_sources, list)
        self.assertGreater(len(rss_sources), 0)


if __name__ == "__main__":
    unittest.main()
