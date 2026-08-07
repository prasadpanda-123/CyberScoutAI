"""
Unit tests for Universal Collection Framework (Phase 3.1).
"""

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.collectors.base import BaseCollector
from src.collectors.cache import CollectorCache
from src.collectors.context import CollectorContext
from src.collectors.factory import CollectorFactory
from src.collectors.http_client import HTTPClient
from src.collectors.manager import CollectorManager
from src.collectors.metrics import CollectorMetrics
from src.collectors.parser_utils import (
    normalize_url,
    parse_html_content,
    parse_json_content,
    parse_rss_xml_content,
)
from src.collectors.rate_limiter import RateLimiter
from src.collectors.registry import CollectorRegistry
from src.collectors.result import CollectorResult
from src.collectors.retry import CollectorRetry
from src.collectors.robots import RobotsChecker
from src.intelligence.planner_models import SearchTask


class DummyCollector(BaseCollector):
    """Concrete dummy collector for framework testing."""

    @property
    def collector_name(self) -> str:
        return "Dummy Collector"

    def collect(self, task: SearchTask) -> CollectorResult:
        return CollectorResult(
            source_id=self.source_id,
            status="success",
            items=[{"title": "Dummy Item"}],
        )


class TestCollectionFramework(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cache.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_metrics(self):
        metrics = CollectorMetrics()
        metrics.record_request(success=True, latency=0.5, num_bytes=100)
        self.assertEqual(metrics.requests_made, 1)
        self.assertEqual(metrics.successful_requests, 1)
        self.assertEqual(metrics.average_latency_seconds, 0.5)

    def test_cache(self):
        cache = CollectorCache(db_path=self.db_path, ttl_seconds=3600)
        cache.set("https://example.com/test", 200, "hello world")
        hit = cache.get("https://example.com/test")
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0], 200)
        self.assertEqual(hit[1], "hello world")

    def test_rate_limiter(self):
        limiter = RateLimiter()
        # Ensure wait executes without error
        limiter.wait(url="https://example.com")

    def test_robots_checker(self):
        checker = RobotsChecker()
        self.assertTrue(checker.is_allowed("https://example.com/allowed"))

    def test_parser_utils(self):
        # JSON
        json_data = parse_json_content('{"key": "value"}')
        self.assertEqual(json_data["key"], "value")

        # HTML
        soup = parse_html_content("<h1>Header</h1>")
        self.assertEqual(soup.find("h1").text, "Header")

        # RSS
        rss_xml = """<rss><channel><item><title>Test Item</title><link>https://example.com</link></item></channel></rss>"""
        items = parse_rss_xml_content(rss_xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Test Item")

        # URL Normalization
        norm = normalize_url("/relative/path", base_url="https://example.com")
        self.assertEqual(norm, "https://example.com/relative/path")

    @patch("requests.Session.get")
    def test_http_client_mocked(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = HTTPClient(cache=CollectorCache(db_path=self.db_path))
        status, text = client.get("https://example.com/api", use_cache=False)
        self.assertEqual(status, 200)
        self.assertIn("status", text)

    def test_registry_and_factory(self):
        registry = CollectorRegistry()
        registry.register(DummyCollector)
        self.assertIn("DummyCollector", registry.list_collectors())

        factory = CollectorFactory(registry=registry)
        collector = factory.create_collector("DummyCollector", source_id="dummy_source")
        self.assertIsNotNone(collector)
        self.assertEqual(collector.source_id, "dummy_source")

    def test_collector_manager_execution(self):
        registry = CollectorRegistry()
        registry.register(DummyCollector)
        manager = CollectorManager(registry=registry)

        task = SearchTask(
            source_id="dummy_source",
            query_text="soc",
            target_url="https://example.com/search",
            category="internship",
            collection_method="rss",
            metadata={"preferred_collector": "DummyCollector"},
        )
        result = manager.execute_task(task)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.items), 1)


if __name__ == "__main__":
    unittest.main()
