"""
Unit Tests for Tavily Search API Client.

Verifies:
- Successful search responses and data parsing
- Missing / invalid API credential handling
- Request timeouts and retry exponential backoff
- Rate limiting (HTTP 429) backoff and error raising
- Empty search results and malformed response handling
- Daily and monthly budget limit enforcement
- Sensitive API key masking in error messages and logs
- Provider health metrics tracking
"""

from io import BytesIO
import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from src.discovery.client_tavily import (
    TavilyAPIError,
    TavilyAuthError,
    TavilyBudgetExceededError,
    TavilyClient,
    TavilyRateLimitError,
    TavilyTimeoutError,
    sanitize_secret,
)
from src.discovery.discovery_models import DiscoveryBudget, SearchQuerySpec, GeographicRegion, OpportunityCategory


class TestTavilyClient:

    def setup_method(self):
        self.mock_key = "tvly-test-1234567890abcdef12345678"
        self.budget = DiscoveryBudget(daily_limit=5, monthly_budget=20, max_searches_per_run=5, max_results_per_query=10)
        self.client = TavilyClient(api_key=self.mock_key, timeout=2.0, max_retries=2, backoff_factor=1.1, budget=self.budget)

    def test_missing_or_placeholder_key_raises_auth_error(self):
        """Client must reject missing or placeholder API keys before making network calls."""
        client_empty = TavilyClient(api_key="")
        with pytest.raises(TavilyAuthError) as exc_info:
            client_empty.search("cybersecurity")
        assert "not configured" in str(exc_info.value)

        client_placeholder = TavilyClient(api_key="your_tavily_api_key_here")
        with pytest.raises(TavilyAuthError):
            client_placeholder.search("cybersecurity")

    @patch("urllib.request.urlopen")
    def test_successful_search_response(self, mock_urlopen):
        """Valid JSON responses must parse and increment health success metrics."""
        mock_response_data = {
            "query": "cybersecurity internship India",
            "results": [
                {
                    "title": "Cyber Security Intern at CERT-In",
                    "url": "https://cert-in.org.in/internship/2026",
                    "content": "Official government cybersecurity internship program in New Delhi.",
                    "score": 0.94,
                },
                {
                    "title": "Unstop Security Hackathon",
                    "url": "https://unstop.com/hackathons/cyber-2026",
                    "content": "Free national cyber security hackathon for college students.",
                    "score": 0.88,
                },
            ]
        }
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        results = self.client.search("cybersecurity internship India")
        assert len(results) == 2
        assert results[0]["title"] == "Cyber Security Intern at CERT-In"
        assert results[0]["score"] == 0.94
        assert self.client.metrics.successful_requests == 1
        assert self.client.metrics.is_healthy is True
        assert self.client.daily_requests_executed == 1

    @patch("urllib.request.urlopen")
    def test_empty_search_results(self, mock_urlopen):
        """Queries returning zero results should return an empty list without error."""
        mock_response_data = {"query": "obscure nonexistent query", "results": []}
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        results = self.client.search("obscure query")
        assert results == []
        assert self.client.metrics.successful_requests == 1

    @patch("urllib.request.urlopen")
    def test_http_401_raises_auth_error(self, mock_urlopen):
        """HTTP 401 unauthorized must raise TavilyAuthError."""
        err_fp = BytesIO(b'{"error": "Unauthorized key"}')
        http_err = urllib.error.HTTPError("https://api.tavily.com", 401, "Unauthorized", {}, err_fp)
        mock_urlopen.side_effect = http_err

        with pytest.raises(TavilyAuthError) as exc_info:
            self.client.search("test")
        assert exc_info.value.status_code == 401
        assert self.client.metrics.failed_requests == 1

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    def test_http_429_rate_limit_retry_and_exhaustion(self, mock_sleep, mock_urlopen):
        """HTTP 429 must trigger exponential backoff retry and raise TavilyRateLimitError when exhausted."""
        err_fp = BytesIO(b'{"error": "Rate limit exceeded"}')
        http_err = urllib.error.HTTPError("https://api.tavily.com", 429, "Too Many Requests", {}, err_fp)
        mock_urlopen.side_effect = http_err

        with pytest.raises(TavilyRateLimitError):
            self.client.search("test query")

        # 1 initial attempt + 2 retries = 3 calls
        assert mock_urlopen.call_count == 3
        assert mock_sleep.call_count == 2
        assert self.client.metrics.rate_limited_requests >= 1

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    def test_transient_500_server_error_recovers_on_retry(self, mock_sleep, mock_urlopen):
        """Transient HTTP 500 error should retry and succeed if subsequent attempt succeeds."""
        err_fp = BytesIO(b'{"error": "Internal Server Error"}')
        http_err = urllib.error.HTTPError("https://api.tavily.com", 500, "Internal Server Error", {}, err_fp)

        mock_success = MagicMock()
        mock_success.read.return_value = json.dumps({"results": [{"title": "Recovered", "url": "https://example.com"}]}).encode("utf-8")
        mock_success.__enter__.return_value = mock_success

        # First call fails with 500, second call succeeds
        mock_urlopen.side_effect = [http_err, mock_success]

        results = self.client.search("resilience test")
        assert len(results) == 1
        assert results[0]["title"] == "Recovered"
        assert mock_urlopen.call_count == 2
        assert mock_sleep.call_count == 1
        assert self.client.metrics.successful_requests == 1

    @patch("urllib.request.urlopen")
    @patch("time.sleep", return_value=None)
    def test_request_timeout_raises_timeout_error(self, mock_sleep, mock_urlopen):
        """Socket timeout across all retries must raise TavilyTimeoutError."""
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        with pytest.raises(TavilyTimeoutError):
            self.client.search("slow query")
        assert mock_urlopen.call_count == 3  # 1 initial + 2 retries

    def test_daily_budget_limit_enforced(self):
        """When daily budget is reached, client must raise TavilyBudgetExceededError without making calls."""
        self.client.daily_requests_executed = self.budget.daily_limit
        with pytest.raises(TavilyBudgetExceededError) as exc_info:
            self.client.search("budget test")
        assert "Daily discovery search budget reached" in str(exc_info.value)

    def test_monthly_budget_limit_enforced(self):
        """When monthly budget is reached, client must raise TavilyBudgetExceededError."""
        self.client.monthly_requests_executed = self.budget.monthly_budget
        with pytest.raises(TavilyBudgetExceededError) as exc_info:
            self.client.search("budget test")
        assert "Monthly discovery search budget reached" in str(exc_info.value)

    def test_secret_sanitization_helper(self):
        """Helper sanitize_secret must reliably mask secret patterns."""
        secret_sample = "Error on query with tvly-1234567890abcdef12345678 token"
        masked = sanitize_secret(secret_sample)
        assert "1234567890abcdef12345678" not in masked
        assert "tvly-[REDACTED]" in masked

        bearer_sample = "Authorization: Bearer my_secret_token_abc"
        masked_bearer = sanitize_secret(bearer_sample)
        assert "my_secret_token_abc" not in masked_bearer
        assert "Bearer [REDACTED]" in masked_bearer

    @patch("urllib.request.urlopen")
    def test_execute_query_spec(self, mock_urlopen):
        """Client must correctly execute structured SearchQuerySpec objects."""
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps({"results": [{"title": "Spec Test", "url": "https://example.com"}]}).encode("utf-8")
        mock_cm.__enter__.return_value = mock_cm
        mock_urlopen.return_value = mock_cm

        spec = SearchQuerySpec(
            query="CTF challenge 2026",
            region=GeographicRegion.INDIA,
            category=OpportunityCategory.CTF,
            include_domains=["ctftime.org"],
            max_results=5,
        )
        res = self.client.execute_query_spec(spec)
        assert len(res) == 1
        assert res[0]["title"] == "Spec Test"

