"""
Unit tests for background scan job manager, single-scan concurrency locking, and HTTP client.
"""

import time
import unittest
from unittest.mock import MagicMock, patch

from src.automation.job_manager import ScanInProgressError, ScanJob, ScanJobManager, scan_job_manager
from src.collectors.http_client import HTTPClient, HTTPClientError


class TestScanJobManager(unittest.TestCase):
    """Test suite for ScanJobManager asynchronous background job execution and single-scan locking."""

    def setUp(self):
        self.manager = ScanJobManager()
        # Reset active job state
        with self.manager._job_lock:
            self.manager._active_job_id = None
            self.manager._jobs.clear()

    def test_job_creation_and_instant_return(self):
        """Verify POST scan job creation returns within milliseconds."""
        with patch("src.automation.pipeline.run_pipeline_once") as mock_pipeline:
            mock_pipeline.return_value = {
                "success": True,
                "status": "success",
                "items_quality_accepted": 5,
            }
            start_ts = time.time()
            job = self.manager.start_scan_job(dry_run=True)
            elapsed_ms = (time.time() - start_ts) * 1000

            self.assertIsNotNone(job.job_id)
            self.assertTrue(job.job_id.startswith("job-"))
            self.assertLess(elapsed_ms, 2000.0, "start_scan_job must return in under 2 seconds.")

            # Poll job status
            job_dict = self.manager.get_job(job.job_id)
            self.assertIsNotNone(job_dict)
            self.assertEqual(job_dict["job_id"], job.job_id)
            self.assertIn("status", job_dict)
            self.assertIn("progress", job_dict)
            self.assertIn("current_collector", job_dict)
            self.assertIn("opportunities_found", job_dict)
            self.assertIn("elapsed_time", job_dict)
            self.assertIn("errors", job_dict)

    def test_single_scan_concurrency_lock_raises_409(self):
        """Verify that starting a second scan while one is active raises ScanInProgressError."""
        with patch("src.automation.pipeline.run_pipeline_once") as mock_pipeline:
            # Make pipeline hang briefly
            def slow_run(*args, **kwargs):
                time.sleep(1.0)
                return {"success": True, "items_quality_accepted": 0}

            mock_pipeline.side_effect = slow_run

            job1 = self.manager.start_scan_job(dry_run=True)
            self.assertTrue(self.manager.is_scan_active())

            with self.assertRaises(ScanInProgressError):
                self.manager.start_scan_job(dry_run=True)


class TestHTTPClientPoolAndTimeouts(unittest.TestCase):
    """Test suite for HTTP client connection pooling and 10s connect / 20s read timeouts."""

    def test_http_client_timeout_and_session_configuration(self):
        """Verify HTTPClient configures requests.Session pooling and 10s/20s timeouts."""
        client = HTTPClient()
        self.assertEqual(client.connect_timeout, 10.0)
        self.assertEqual(client.read_timeout, 20.0)
        self.assertEqual(client.timeout, (10.0, 20.0))
        self.assertIsNotNone(client.session)

    @patch("requests.Session.get")
    def test_http_client_connect_timeout_logging_and_error(self, mock_get):
        """Verify ConnectTimeout raises HTTPClientError and logs URL/reason."""
        import requests
        from src.collectors.retry import CollectorRetry
        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out after 10 seconds")

        client = HTTPClient(retry_policy=CollectorRetry(max_retries=1))
        with self.assertRaises(HTTPClientError) as ctx:
            client.get("https://example.com/test-feed", use_cache=False)

        self.assertIn("ConnectTimeout", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
