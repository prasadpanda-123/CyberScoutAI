"""
Unit tests for HtmlScraperCollector.
"""

import unittest
from unittest.mock import patch

from src.collectors.context import CollectorContext
from src.collectors.html_collector import HtmlScraperCollector
from src.collectors.registry import CollectorRegistry
from src.intelligence.planner_models import SearchTask


class TestHtmlScraperCollector(unittest.TestCase):
    def setUp(self):
        self.context = CollectorContext.create_default()
        self.collector = HtmlScraperCollector(context=self.context)

    def test_registry_includes_html_scraper(self):
        """Verify CollectorRegistry contains HtmlScraperCollector."""
        registry = CollectorRegistry()
        self.assertIn("HtmlScraperCollector", registry.list_collectors())

    def test_html_scraper_successful_collection(self):
        """Verify HtmlScraperCollector extracts links from valid HTML string."""
        task = SearchTask(
            source_id="test_html",
            query_text="courses",
            target_url="https://example.com/courses",
            category="course",
            collection_method="html",
        )
        sample_html = "<html><body><a href='https://example.com/course/1'>Web Hacking Course 101</a></body></html>"
        with patch.object(self.context.http_client, "get", return_value=(200, sample_html)):
            result = self.collector.collect(task)
            self.assertIn(result.status, ["success", "partial"])
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0]["title"], "Web Hacking Course 101")


if __name__ == "__main__":
    unittest.main()
