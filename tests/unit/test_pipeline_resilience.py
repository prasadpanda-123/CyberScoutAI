"""
Unit tests for Pipeline Resilience & Exception Isolation Framework.
"""

import socket
import ssl
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from src.collectors.base import BaseCollector
from src.collectors.exceptions import CollectorError
from src.collectors.manager import CollectorManager
from src.collectors.result import CollectorResult
from src.intelligence.planner_models import SearchPlan, SearchTask


class FailingCollector(BaseCollector):
    """Mock collector that raises simulated network/parsing exceptions."""

    def __init__(self, exception_to_raise: Exception):
        super().__init__(source_id="failing_source")
        self.exception_to_raise = exception_to_raise

    @property
    def collector_name(self) -> str:
        return "Failing Collector"

    def collect(self, task: SearchTask) -> CollectorResult:
        raise self.exception_to_raise


class TestPipelineResilience(unittest.TestCase):
    """Tests exception isolation and pipeline resilience across failure modes."""

    def setUp(self):
        self.manager = CollectorManager()

    def test_pipeline_resilience_http_404_500(self):
        """Verify HTTP 404 / 500 errors are caught without stopping the pipeline."""
        task = SearchTask(
            source_id="test_404",
            query_text="",
            target_url="https://example.com/404",
            category="security_news",
            collection_method="rss",
        )
        col = FailingCollector(urllib.error.HTTPError("https://example.com/404", 404, "Not Found", {}, None))
        res = self.manager.execute_task(task, collector=col)

        self.assertEqual(res.status, "failed")
        self.assertIn("HTTP 404", res.errors[0])
        self.assertEqual(self.manager.metrics.providers_failed, 1)

    def test_pipeline_resilience_timeout_error(self):
        """Verify socket / connection timeouts are caught and recorded."""
        task = SearchTask(
            source_id="test_timeout",
            query_text="",
            target_url="https://example.com/timeout",
            category="security_news",
            collection_method="rss",
        )
        col = FailingCollector(socket.timeout("Connection timed out after 15s"))
        res = self.manager.execute_task(task, collector=col)

        self.assertEqual(res.status, "failed")
        self.assertIn("Timeout", res.errors[0])
        self.assertEqual(self.manager.metrics.timeouts_count, 1)

    def test_pipeline_resilience_ssl_error(self):
        """Verify SSL verification failures are caught and recorded."""
        task = SearchTask(
            source_id="test_ssl",
            query_text="",
            target_url="https://example.com/ssl",
            category="security_news",
            collection_method="rss",
        )
        col = FailingCollector(ssl.SSLError("CERTIFICATE_VERIFY_FAILED"))
        res = self.manager.execute_task(task, collector=col)

        self.assertEqual(res.status, "failed")
        self.assertIn("SSL error", res.errors[0])
        self.assertEqual(self.manager.metrics.providers_failed, 1)

    def test_pipeline_resilience_generic_exception(self):
        """Verify generic unhandled exceptions do not abort execution."""
        task = SearchTask(
            source_id="test_generic",
            query_text="",
            target_url="https://example.com/err",
            category="security_news",
            collection_method="rss",
        )
        col = FailingCollector(ValueError("Unexpected payload structure"))
        res = self.manager.execute_task(task, collector=col)

        self.assertEqual(res.status, "failed")
        self.assertIn("Collector exception", res.errors[0])

    def test_execute_plan_completes_even_if_all_tasks_fail(self):
        """Verify execute_plan finishes cleanly even when all providers fail."""
        tasks = [
            SearchTask(source_id=f"source_{i}", query_text="", target_url=f"https://example.com/{i}", category="security_news", collection_method="rss")
            for i in range(10)
        ]
        plan = SearchPlan(tasks=tasks)

        with patch.object(self.manager, "execute_task") as mock_exec:
            mock_exec.return_value = CollectorResult(source_id="mock", status="failed", errors=["Mock failure"])
            results = self.manager.execute_plan(plan)

            self.assertEqual(len(results), 10)
            for r in results:
                self.assertEqual(r.status, "failed")


if __name__ == "__main__":
    unittest.main()
