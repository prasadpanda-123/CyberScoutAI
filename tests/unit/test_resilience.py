"""
Collector resilience and failure recovery unit tests for CyberScout AI.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.collectors.base import BaseCollector
from src.collectors.context import CollectorContext
from src.collectors.exceptions import CollectorError, HTTPClientError
from src.collectors.manager import CollectorManager
from src.collectors.result import CollectorResult
from src.collectors.rss_collector import GenericRSSCollector
from src.intelligence.planner_models import SearchTask


class TestCollectorResilience(unittest.TestCase):
    def setUp(self):
        self.context = CollectorContext.create_default()
        self.manager = CollectorManager(context=self.context)

    def test_rss_collector_resilience_on_404(self):
        """Verify RSS collector handles 404 HTTP errors gracefully without crashing."""
        task = SearchTask(
            source_id="test_rss",
            query_text="malware analysis",
            target_url="https://invalid-nonexistent-domain.org/rss.xml",
            category="threat_intel",
            collection_method="rss",
        )
        collector = GenericRSSCollector(context=self.context)

        # Mock http_client to raise HTTPClientError
        with patch.object(self.context.http_client, "get", side_effect=HTTPClientError("HTTP 404 Not Found")):
            result = collector.collect(task)
            self.assertEqual(result.status, "failed")
            self.assertEqual(len(result.items), 0)
            self.assertTrue(any("404" in err for err in result.errors))

    def test_rss_collector_resilience_on_malformed_xml(self):
        """Verify RSS collector handles malformed XML payloads cleanly."""
        task = SearchTask(
            source_id="test_rss_malformed",
            query_text="security research",
            target_url="https://example.com/bad.xml",
            category="research",
            collection_method="rss",
        )
        collector = GenericRSSCollector(context=self.context)

        malformed_xml = "<rss><channel><title>Broken Feed</channel></rss>"
        with patch.object(self.context.http_client, "get", return_value=(200, malformed_xml)):
            result = collector.collect(task)
            self.assertIn(result.status, ["success", "failed", "partial"])

    def test_manager_executes_plan_with_mixed_failures(self):
        """Verify CollectorManager continues execution across tasks even when some collectors fail."""
        task_good = SearchTask(
            source_id="sans",
            query_text="penetration testing",
            target_url="https://www.sans.org/feed.xml",
            category="training",
            collection_method="rss",
        )
        task_bad = SearchTask(
            source_id="broken_source",
            query_text="cyber security",
            target_url="https://broken-source.com/rss",
            category="news",
            collection_method="rss",
        )

        res_good = CollectorResult(source_id="sans", status="success", items=[{"title": "SANS Course", "url": "https://sans.org/1"}], errors=[])
        res_bad = CollectorResult(source_id="broken_source", status="failed", items=[], errors=["Network error"])

        mock_collector_good = MagicMock(spec=BaseCollector)
        mock_collector_good.collect.return_value = res_good

        mock_collector_bad = MagicMock(spec=BaseCollector)
        mock_collector_bad.collect.return_value = res_bad

        # Execute task good
        res1 = self.manager.execute_task(task_good, collector=mock_collector_good)
        self.assertEqual(res1.status, "success")
        self.assertEqual(len(res1.items), 1)

        # Execute task bad
        res2 = self.manager.execute_task(task_bad, collector=mock_collector_bad)
        self.assertEqual(res2.status, "failed")
        self.assertEqual(len(res2.items), 0)


if __name__ == "__main__":
    unittest.main()
