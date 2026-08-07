"""
Unit tests for ScanJob dataclass, ScanJobManager concurrency lock, and HTTPClient timeout behaviour.
These tests are fully synchronous — no real network calls, no background threads blocking pytest.
"""

import threading
import unittest
from unittest.mock import MagicMock, patch

from src.automation.job_manager import ScanInProgressError, ScanJob, ScanJobManager


def _make_fresh_manager() -> ScanJobManager:
    """Bypass singleton pattern to get a fresh, isolated ScanJobManager per test."""
    mgr = object.__new__(ScanJobManager)
    mgr._jobs = {}
    mgr._active_job_id = None
    mgr._job_lock = threading.RLock()
    mgr._initialized = True
    return mgr


class TestScanJobDataclass(unittest.TestCase):
    """Unit tests for ScanJob dataclass serialization."""

    def test_job_to_dict_contains_all_required_fields(self):
        """Verify ScanJob.to_dict() returns all 9 expected API fields."""
        job = ScanJob(job_id="job-abc123")
        d = job.to_dict()
        for field in ["job_id", "status", "progress", "current_collector",
                      "opportunities_found", "elapsed_time", "errors",
                      "created_at", "started_at"]:
            self.assertIn(field, d, f"Missing field: {field}")

    def test_job_progress_rounded(self):
        """Verify progress is rounded to 1 decimal place."""
        job = ScanJob(job_id="job-xyz", progress=66.6666)
        d = job.to_dict()
        self.assertEqual(d["progress"], 66.7)

    def test_job_errors_list(self):
        """Verify errors field is a list."""
        job = ScanJob(job_id="job-err", errors=["something failed"])
        d = job.to_dict()
        self.assertIsInstance(d["errors"], list)
        self.assertEqual(len(d["errors"]), 1)


class TestScanJobManagerState(unittest.TestCase):
    """Unit tests for ScanJobManager state management — no background threads."""

    def test_is_scan_active_false_when_no_job(self):
        """Verify is_scan_active returns False when no active job exists."""
        mgr = _make_fresh_manager()
        self.assertFalse(mgr.is_scan_active())

    def test_is_scan_active_true_for_running_job(self):
        """Verify is_scan_active returns True when a running job is set."""
        mgr = _make_fresh_manager()
        job = ScanJob(job_id="job-running-001", status="collecting")
        mgr._jobs["job-running-001"] = job
        mgr._active_job_id = "job-running-001"
        self.assertTrue(mgr.is_scan_active())

    def test_is_scan_active_false_after_job_completed(self):
        """Verify is_scan_active clears _active_job_id when job reaches completed state."""
        mgr = _make_fresh_manager()
        job = ScanJob(job_id="job-done-001", status="completed")
        mgr._jobs["job-done-001"] = job
        mgr._active_job_id = "job-done-001"
        self.assertFalse(mgr.is_scan_active())
        self.assertIsNone(mgr._active_job_id)

    def test_get_job_returns_none_for_unknown_id(self):
        """Verify get_job returns None for an unknown job ID."""
        mgr = _make_fresh_manager()
        self.assertIsNone(mgr.get_job("does-not-exist"))

    def test_get_job_returns_valid_dict(self):
        """Verify get_job returns a correct dict for a known job."""
        mgr = _make_fresh_manager()
        job = ScanJob(job_id="job-known", status="completed", progress=100.0, opportunities_found=7)
        mgr._jobs["job-known"] = job
        result = mgr.get_job("job-known")
        self.assertIsNotNone(result)
        self.assertEqual(result["job_id"], "job-known")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["opportunities_found"], 7)

    def test_concurrency_lock_raises_scan_in_progress_error(self):
        """Verify ScanInProgressError is raised immediately when a scan is already active."""
        mgr = _make_fresh_manager()
        # Inject an active job directly into state — no background thread needed
        active_job = ScanJob(job_id="job-active", status="processing")
        mgr._jobs["job-active"] = active_job
        mgr._active_job_id = "job-active"

        with self.assertRaises(ScanInProgressError) as ctx:
            mgr.start_scan_job(dry_run=True)

        self.assertIn("job-active", str(ctx.exception))

    def test_scan_in_progress_error_message_contains_job_id(self):
        """Verify ScanInProgressError message includes the active job ID."""
        mgr = _make_fresh_manager()
        mgr._jobs["job-xyz"] = ScanJob(job_id="job-xyz", status="running")
        mgr._active_job_id = "job-xyz"

        try:
            mgr.start_scan_job(dry_run=True)
            self.fail("Expected ScanInProgressError was not raised")
        except ScanInProgressError as e:
            self.assertIn("job-xyz", str(e))


class TestHTTPClientConfiguration(unittest.TestCase):
    """Test HTTPClient initializes with correct connection pooling and timeout defaults."""

    def test_http_client_timeout_defaults(self):
        """Verify HTTPClient has 10s connect and 20s read timeout defaults."""
        # We only test attribute values — no actual HTTP request is made
        from src.collectors.http_client import HTTPClient
        from src.collectors.rate_limiter import RateLimiter

        # Use a zero-delay rate limiter so no sleep occurs on import
        rl = object.__new__(RateLimiter)
        rl.default_delay = 0.0
        rl.source_limits = {}
        rl.last_request_times = {}
        rl.config_file = None

        client = HTTPClient(rate_limiter=rl)
        self.assertEqual(client.connect_timeout, 10.0)
        self.assertEqual(client.read_timeout, 20.0)
        self.assertEqual(client.timeout, (10.0, 20.0))
        self.assertIsNotNone(client.session)

    def test_http_client_connect_timeout_raises_http_client_error(self):
        """Verify ConnectTimeout from requests is wrapped in HTTPClientError."""
        import requests
        from src.collectors.http_client import HTTPClient, HTTPClientError
        from src.collectors.rate_limiter import RateLimiter
        from src.collectors.retry import CollectorRetry

        rl = object.__new__(RateLimiter)
        rl.default_delay = 0.0
        rl.source_limits = {}
        rl.last_request_times = {}
        rl.config_file = None

        retry = CollectorRetry(max_attempts=1, initial_delay=0.0)
        client = HTTPClient(rate_limiter=rl, retry_policy=retry)

        with patch.object(client.session, "get",
                          side_effect=requests.exceptions.ConnectTimeout("host timeout")):
            with self.assertRaises(HTTPClientError) as ctx:
                client.get("https://example.com/feed", use_cache=False)
            self.assertIn("ConnectTimeout", str(ctx.exception))

    def test_http_client_read_timeout_raises_http_client_error(self):
        """Verify ReadTimeout from requests is wrapped in HTTPClientError."""
        import requests
        from src.collectors.http_client import HTTPClient, HTTPClientError
        from src.collectors.rate_limiter import RateLimiter
        from src.collectors.retry import CollectorRetry

        rl = object.__new__(RateLimiter)
        rl.default_delay = 0.0
        rl.source_limits = {}
        rl.last_request_times = {}
        rl.config_file = None

        retry = CollectorRetry(max_attempts=1, initial_delay=0.0)
        client = HTTPClient(rate_limiter=rl, retry_policy=retry)

        with patch.object(client.session, "get",
                          side_effect=requests.exceptions.ReadTimeout("read timeout")):
            with self.assertRaises(HTTPClientError) as ctx:
                client.get("https://example.com/slow", use_cache=False)
            self.assertIn("ReadTimeout", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
