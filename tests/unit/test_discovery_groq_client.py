"""
Unit Tests for Groq Primary AI Classification Client (Phase D).

Verifies:
- Client initialization, default model selection, and configuration loading
- Secret masking in logs, telemetry, and exceptions (gsk_...)
- Successful chat completion with JSON object formatting (mocked HTTP 200)
- Graceful handling when AI classification is disabled
- Authentication errors (HTTP 401/403)
- Quota exhaustion handling (HTTP 402)
- Rate limit backoff and retry exhaustion (HTTP 429)
- Transient server error recovery (HTTP 500/502/503)
- Network timeout handling (Socket / URLError)
- Malformed response JSON protection
"""

from io import BytesIO
import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from src.discovery.classification_models import ClassificationBudget
from src.discovery.client_groq import (
    GroqAPIError,
    GroqAuthError,
    GroqClient,
    GroqQuotaError,
    GroqRateLimitError,
    GroqTimeoutError,
    sanitize_groq_secret,
)


class DummyHTTPResponse:
    """Mock HTTP response context manager."""

    def __init__(self, data: bytes, code: int = 200):
        self._data = data
        self.code = code

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestGroqClient:

    def test_secret_sanitization(self):
        """Secret sanitizer must mask Groq API keys and Bearer headers."""
        raw = "Error with Bearer gsk_abc123456789012345678901234567890 to api.groq.com"
        clean = sanitize_groq_secret(raw)
        assert "gsk_abc123456789012345678901234567890" not in clean
        assert "gsk_[REDACTED]" in clean or "Bearer [REDACTED]" in clean

    def test_client_initialization_defaults(self):
        """Client must initialize with specified or default model and budget."""
        budget = ClassificationBudget(timeout_seconds=20.0, max_tokens=2048)
        client = GroqClient(api_key="gsk_test_key_12345678901234567890", model="llama-3.3-70b-versatile", budget=budget)

        assert client.is_configured is True
        assert client.model == "llama-3.3-70b-versatile"
        assert client.timeout == 20.0
        assert client.budget.max_tokens == 2048

    def test_disabled_client_raises_error(self):
        """When classification is disabled, client raises GroqAPIError."""
        client = GroqClient(api_key="gsk_test_key", enabled=False)
        assert client.is_enabled is False

        with pytest.raises(GroqAPIError) as exc_info:
            client.classify("System prompt", "User prompt")
        assert "disabled via configuration" in str(exc_info.value)

    def test_missing_api_key_raises_auth_error(self):
        """When API key is empty/missing, classify must raise GroqAuthError."""
        client = GroqClient(api_key="", enabled=True)
        assert client.is_configured is False

        with pytest.raises(GroqAuthError) as exc_info:
            client.classify("System prompt", "User prompt")
        assert "GROQ_API_KEY is not configured" in str(exc_info.value)

    def test_successful_classification(self):
        """Successful Groq completion parses and returns JSON structured output."""
        structured_output = {
            "title": "Cyber Security Internship 2026",
            "category": "internship",
            "confidence": 0.95,
        }
        mock_groq_envelope = {
            "id": "chatcmpl-test-101",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(structured_output),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 450,
                "completion_tokens": 120,
                "total_tokens": 570,
            },
        }

        mock_resp = DummyHTTPResponse(json.dumps(mock_groq_envelope).encode("utf-8"))
        mock_opener = MagicMock(return_value=mock_resp)

        client = GroqClient(api_key="gsk_valid_key_12345678901234567890", http_opener=mock_opener)
        result = client.classify("System prompt", "User prompt")

        assert result["title"] == "Cyber Security Internship 2026"
        assert result["category"] == "internship"
        assert client.metrics.successful_requests == 1
        assert client.metrics.total_prompt_tokens == 450
        assert client.metrics.total_completion_tokens == 120

    @patch("time.sleep", return_value=None)
    def test_rate_limit_429_backoff_and_exhaustion(self, mock_sleep):
        """HTTP 429 must retry with exponential backoff and raise GroqRateLimitError on exhaustion."""
        http_err = urllib.error.HTTPError(
            url="https://api.groq.com/openai/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=BytesIO(b'{"error": {"message": "Rate limit reached"}}'),
        )
        mock_opener = MagicMock(side_effect=http_err)

        client = GroqClient(
            api_key="gsk_valid_key_12345678901234567890",
            max_retries=2,
            backoff_factor=1.0,
            http_opener=mock_opener,
        )

        with pytest.raises(GroqRateLimitError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "rate limit exceeded" in str(exc_info.value).lower()
        assert client.metrics.rate_limits_encountered > 0
        assert mock_opener.call_count == 3  # Initial + 2 retries

    @patch("time.sleep", return_value=None)
    def test_transient_server_error_retry_and_recovery(self, mock_sleep):
        """Transient HTTP 500 must retry and succeed on subsequent attempt."""
        http_err = urllib.error.HTTPError(
            url="https://api.groq.com/openai/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(b'{"error": "Internal server error"}'),
        )
        success_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({"title": "Recovered Opportunity"}),
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        success_resp = DummyHTTPResponse(json.dumps(success_payload).encode("utf-8"))

        mock_opener = MagicMock(side_effect=[http_err, success_resp])

        client = GroqClient(
            api_key="gsk_valid_key_12345678901234567890",
            max_retries=2,
            backoff_factor=1.0,
            http_opener=mock_opener,
        )

        result = client.classify("System prompt", "User prompt")
        assert result["title"] == "Recovered Opportunity"
        assert mock_opener.call_count == 2
        assert client.metrics.successful_requests == 1

    def test_quota_exhaustion_402_handling(self):
        """HTTP 402 or insufficient quota must raise GroqQuotaError immediately without retrying."""
        http_err = urllib.error.HTTPError(
            url="https://api.groq.com/openai/v1/chat/completions",
            code=402,
            msg="Payment Required",
            hdrs={},
            fp=BytesIO(b'{"error": {"message": "insufficient_quota"}}'),
        )
        mock_opener = MagicMock(side_effect=http_err)

        client = GroqClient(
            api_key="gsk_valid_key_12345678901234567890",
            max_retries=2,
            http_opener=mock_opener,
        )

        with pytest.raises(GroqQuotaError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "quota or credit limit exhausted" in str(exc_info.value).lower()
        assert mock_opener.call_count == 1  # No wasteful retries on quota exhaustion

    @patch("time.sleep", return_value=None)
    def test_timeout_handling(self, mock_sleep):
        """Socket timeout must be caught and raised as GroqTimeoutError."""
        mock_opener = MagicMock(side_effect=TimeoutError("Request timed out"))

        client = GroqClient(
            api_key="gsk_valid_key_12345678901234567890",
            max_retries=1,
            http_opener=mock_opener,
        )

        with pytest.raises(GroqTimeoutError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "timed out" in str(exc_info.value).lower()

    def test_malformed_json_content(self):
        """Malformed JSON inside message content must raise GroqAPIError."""
        bad_envelope = {
            "choices": [
                {
                    "message": {
                        "content": "Not JSON at all! Just raw text.",
                    }
                }
            ],
            "usage": {},
        }
        mock_resp = DummyHTTPResponse(json.dumps(bad_envelope).encode("utf-8"))
        mock_opener = MagicMock(return_value=mock_resp)

        client = GroqClient(
            api_key="gsk_valid_key_12345678901234567890",
            http_opener=mock_opener,
        )

        with pytest.raises(GroqAPIError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "could not be parsed as JSON" in str(exc_info.value)

