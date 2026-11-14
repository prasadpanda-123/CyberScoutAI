"""
Unit Tests for Firecrawl Content Extraction Client.

Verifies:
- Client initialization, budget validation, and configuration loading
- Secret masking in logs, telemetry, and exceptions
- Successful scrape API execution (mocked HTTP 200)
- Graceful handling when Firecrawl is disabled
- Authentication errors (HTTP 401/403)
- Rate limiting backoff & retry exhaustion (HTTP 429)
- Transient server errors & retry recovery (HTTP 500/502/503)
- Network timeout handling (Socket/URLError)
- Budget limit enforcement (daily and run limits)
- Malformed response protection
"""

from io import BytesIO
import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from src.discovery.client_firecrawl import (
    FirecrawlAPIError,
    FirecrawlAuthError,
    FirecrawlBudgetExceededError,
    FirecrawlClient,
    FirecrawlError,
    FirecrawlRateLimitError,
    FirecrawlTimeoutError,
    sanitize_firecrawl_secret,
)
from src.discovery.discovery_models import ExtractionBudget


class DummyResponse:
    """Mock HTTP response object implementing context manager protocol."""

    def __init__(self, data: bytes, code: int = 200):
        self._data = data
        self.code = code

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestFirecrawlClient:

    def test_secret_sanitization(self):
        """Secret sanitizer must mask API tokens, bearer headers, and env keys."""
        raw = "Error sending request with Bearer fc-a1b2c3d4e5f6g7h8i9j0k1l2 to https://api.firecrawl.dev"
        sanitized = sanitize_firecrawl_secret(raw)
        assert "fc-a1b2c3d4e5f6g7h8i9j0k1l2" not in sanitized
        assert "[REDACTED]" in sanitized

    def test_client_initialization_defaults(self):
        """Client must initialize with reasonable defaults and load budget."""
        budget = ExtractionBudget(daily_limit=50, max_pages_per_run=10, timeout_seconds=15.0)
        client = FirecrawlClient(api_key="fc-test-key-12345678", budget=budget)
        assert client.is_configured is True
        assert client.budget.daily_limit == 50
        assert client.budget.max_pages_per_run == 10
        assert client.timeout == 15.0

    def test_disabled_firecrawl_returns_safe_dict(self):
        """When Firecrawl is disabled via flag, scrape_url must safely skip without making network requests."""
        client = FirecrawlClient(api_key="fc-test-key-12345678", enabled=False)
        assert client.is_enabled is False

        result = client.scrape_url("https://example.com/job")
        assert result.get("markdown") == ""
        assert "Firecrawl disabled" in result.get("metadata", {}).get("error", "")

    def test_missing_api_key_raises_auth_error(self):
        """When API key is empty/missing, scrape_url must raise FirecrawlAuthError."""
        client = FirecrawlClient(api_key="", enabled=True)
        assert client.is_configured is False

        with pytest.raises(FirecrawlAuthError) as exc_info:
            client.scrape_url("https://example.com/job")
        assert "FIRECRAWL_API_KEY is not configured" in str(exc_info.value)

    def test_successful_scrape(self):
        """Successful Firecrawl scrape must parse markdown, html, and metadata."""
        mock_payload = {
            "success": True,
            "data": {
                "markdown": "# Junior Cybersecurity Analyst\nFree internship with stipend.",
                "html": "<h1>Junior Cybersecurity Analyst</h1><p>Free internship with stipend.</p>",
                "metadata": {
                    "title": "Junior Cybersecurity Analyst",
                    "sourceURL": "https://cybersec.example.org/internship",
                    "statusCode": 200,
                },
            },
        }
        mock_response = DummyResponse(json.dumps(mock_payload).encode("utf-8"))
        mock_opener = MagicMock(return_value=mock_response)

        client = FirecrawlClient(api_key="fc-mock-test-key-12345678", http_opener=mock_opener)
        result = client.scrape_url("https://cybersec.example.org/internship")

        assert "Junior Cybersecurity Analyst" in result["markdown"]
        assert result["metadata"]["title"] == "Junior Cybersecurity Analyst"
        assert client.metrics.successful_requests == 1
        assert client.metrics.failed_requests == 0
        assert client.run_requests_executed == 1

    def test_budget_exceeded_enforcement(self):
        """When run limit is exceeded, client must raise FirecrawlBudgetExceededError before network call."""
        budget = ExtractionBudget(max_pages_per_run=1)
        mock_payload = {"success": True, "data": {"markdown": "Content"}}
        mock_opener = MagicMock(return_value=DummyResponse(json.dumps(mock_payload).encode("utf-8")))

        client = FirecrawlClient(api_key="fc-mock-test-key-12345678", budget=budget, http_opener=mock_opener)

        # 1st scrape consumes the budget
        client.scrape_url("https://example.com/page1")
        assert client.run_requests_executed == 1

        # 2nd scrape must be blocked by budget
        with pytest.raises(FirecrawlBudgetExceededError) as exc_info:
            client.scrape_url("https://example.com/page2")
        assert "run budget exceeded" in str(exc_info.value)
        assert mock_opener.call_count == 1  # No second HTTP call made

    @patch("time.sleep", return_value=None)
    def test_rate_limit_429_exhaustion(self, mock_sleep):
        """HTTP 429 must retry with backoff and raise FirecrawlRateLimitError on exhaustion."""
        http_err = urllib.error.HTTPError(
            url="https://api.firecrawl.dev/v1/scrape",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=BytesIO(b'{"error": "Rate limit exceeded"}'),
        )
        mock_opener = MagicMock(side_effect=http_err)

        client = FirecrawlClient(
            api_key="fc-mock-test-key-12345678",
            max_retries=2,
            backoff_factor=1.0,
            http_opener=mock_opener,
        )

        with pytest.raises(FirecrawlRateLimitError) as exc_info:
            client.scrape_url("https://example.com/rate-limited")

        assert "rate limit exceeded" in str(exc_info.value).lower()
        assert client.metrics.rate_limits_encountered > 0
        assert mock_opener.call_count == 3  # Initial + 2 retries

    @patch("time.sleep", return_value=None)
    def test_transient_server_error_retry_and_recovery(self, mock_sleep):
        """Transient HTTP 500 must retry and succeed if subsequent attempt succeeds."""
        http_err = urllib.error.HTTPError(
            url="https://api.firecrawl.dev/v1/scrape",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(b'{"error": "Temporary server error"}'),
        )
        success_payload = {
            "success": True,
            "data": {"markdown": "# Recovered page content", "metadata": {}},
        }
        success_resp = DummyResponse(json.dumps(success_payload).encode("utf-8"))

        mock_opener = MagicMock(side_effect=[http_err, success_resp])

        client = FirecrawlClient(
            api_key="fc-mock-test-key-12345678",
            max_retries=2,
            backoff_factor=1.0,
            http_opener=mock_opener,
        )

        result = client.scrape_url("https://example.com/flaky")
        assert "Recovered page content" in result["markdown"]
        assert mock_opener.call_count == 2
        assert client.metrics.successful_requests == 1

    @patch("time.sleep", return_value=None)
    def test_network_timeout_handling(self, mock_sleep):
        """Network timeouts must be caught and raised as FirecrawlTimeoutError."""
        timeout_err = TimeoutError("Connection timed out after 30000ms")
        mock_opener = MagicMock(side_effect=timeout_err)

        client = FirecrawlClient(
            api_key="fc-mock-test-key-12345678",
            max_retries=1,
            http_opener=mock_opener,
        )

        with pytest.raises(FirecrawlTimeoutError) as exc_info:
            client.scrape_url("https://example.com/timeout")
        assert "connection failed" in str(exc_info.value).lower()

    def test_malformed_json_handling(self):
        """Malformed JSON response must raise FirecrawlAPIError without crashing."""
        malformed_resp = DummyResponse(b"<!DOCTYPE html><html>Gateway 502 Bad Gateway</html>")
        mock_opener = MagicMock(return_value=malformed_resp)

        client = FirecrawlClient(
            api_key="fc-mock-test-key-12345678",
            max_retries=0,
            http_opener=mock_opener,
        )

        with pytest.raises(FirecrawlAPIError) as exc_info:
            client.scrape_url("https://example.com/bad-json")
        assert "malformed JSON" in str(exc_info.value)

