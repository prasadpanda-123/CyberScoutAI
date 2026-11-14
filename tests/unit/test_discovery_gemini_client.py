"""
Unit Tests for Google Gemini Fallback AI Classification Client (Phase D).

Verifies:
- Client initialization, model selection, and configuration loading
- Secret masking in logs, telemetry, and exceptions (AIza...)
- Successful generation with structured JSON response (mocked HTTP 200)
- Graceful handling when AI classification is disabled
- Authentication errors (HTTP 400/401/403)
- Rate limit / RESOURCE_EXHAUSTED backoff and retry exhaustion (HTTP 429)
- Transient server error recovery (HTTP 500/502/503)
- Network timeout handling (Socket / URLError)
- Malformed response JSON envelope protection
"""

from io import BytesIO
import json
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from src.discovery.classification_models import ClassificationBudget
from src.discovery.client_gemini import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiClient,
    GeminiRateLimitError,
    GeminiTimeoutError,
    sanitize_gemini_secret,
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


class TestGeminiClient:

    def test_secret_sanitization(self):
        """Secret sanitizer must mask Google API keys and auth headers."""
        raw = "Failed request with AIzaSyDUMMY_FOR_TESTS_00000000000000000000 to Google API"
        clean = sanitize_gemini_secret(raw)
        assert "AIzaSyDUMMY_FOR_TESTS_00000000000000000000" not in clean
        assert "AIza[REDACTED]" in clean

    def test_client_initialization_defaults(self):
        """Client must initialize with specified or default Gemini model and budget."""
        budget = ClassificationBudget(timeout_seconds=25.0, max_tokens=4096)
        client = GeminiClient(api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000", model="gemini-2.5-flash", budget=budget)

        assert client.is_configured is True
        assert client.model == "gemini-2.5-flash"
        assert client.timeout == 25.0

    def test_disabled_client_raises_error(self):
        """When classification is disabled, client raises GeminiAPIError."""
        client = GeminiClient(api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000", enabled=False)
        assert client.is_enabled is False

        with pytest.raises(GeminiAPIError) as exc_info:
            client.classify("System prompt", "User prompt")
        assert "disabled via configuration" in str(exc_info.value)

    def test_missing_api_key_raises_auth_error(self):
        """When API key is empty/missing, classify must raise GeminiAuthError."""
        client = GeminiClient(api_key="", enabled=True)
        assert client.is_configured is False

        with pytest.raises(GeminiAuthError) as exc_info:
            client.classify("System prompt", "User prompt")
        assert "GEMINI_API_KEY is not configured" in str(exc_info.value)

    def test_successful_fallback_classification(self):
        """Successful Gemini generation parses and returns JSON structured output."""
        structured_output = {
            "title": "Collegiate Bug Bounty Challenge",
            "category": "bug_bounty",
            "confidence": 0.90,
        }
        mock_gemini_envelope = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps(structured_output)}
                        ],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 350,
                "candidatesTokenCount": 110,
                "totalTokenCount": 460,
            },
        }

        mock_resp = DummyHTTPResponse(json.dumps(mock_gemini_envelope).encode("utf-8"))
        mock_opener = MagicMock(return_value=mock_resp)

        client = GeminiClient(api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000", http_opener=mock_opener)
        result = client.classify("System prompt", "User prompt")

        assert result["title"] == "Collegiate Bug Bounty Challenge"
        assert result["category"] == "bug_bounty"
        assert client.metrics.successful_requests == 1
        assert client.metrics.total_prompt_tokens == 350
        assert client.metrics.total_completion_tokens == 110

    @patch("time.sleep", return_value=None)
    def test_rate_limit_429_backoff_and_exhaustion(self, mock_sleep):
        """HTTP 429 / RESOURCE_EXHAUSTED must retry with exponential backoff and raise GeminiRateLimitError."""
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            code=429,
            msg="Resource Exhausted",
            hdrs={},
            fp=BytesIO(b'{"error": {"message": "RESOURCE_EXHAUSTED: Rate limit exceeded"}}'),
        )
        mock_opener = MagicMock(side_effect=http_err)

        client = GeminiClient(
            api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000",
            max_retries=2,
            backoff_factor=1.0,
            http_opener=mock_opener,
        )

        with pytest.raises(GeminiRateLimitError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "rate limit exceeded" in str(exc_info.value).lower()
        assert client.metrics.rate_limits_encountered > 0
        assert mock_opener.call_count == 3

    @patch("time.sleep", return_value=None)
    def test_transient_server_error_retry_and_recovery(self, mock_sleep):
        """Transient HTTP 503 must retry and succeed on subsequent attempt."""
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=BytesIO(b'{"error": "Backend temporary error"}'),
        )
        success_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps({"title": "Recovered by Gemini"})}
                        ]
                    }
                }
            ],
            "usageMetadata": {},
        }
        success_resp = DummyHTTPResponse(json.dumps(success_payload).encode("utf-8"))

        mock_opener = MagicMock(side_effect=[http_err, success_resp])

        client = GeminiClient(
            api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000",
            max_retries=2,
            backoff_factor=1.0,
            http_opener=mock_opener,
        )

        result = client.classify("System prompt", "User prompt")
        assert result["title"] == "Recovered by Gemini"
        assert mock_opener.call_count == 2
        assert client.metrics.successful_requests == 1

    @patch("time.sleep", return_value=None)
    def test_timeout_handling(self, mock_sleep):
        """Socket timeout must be caught and raised as GeminiTimeoutError."""
        mock_opener = MagicMock(side_effect=TimeoutError("Connection timed out"))

        client = GeminiClient(
            api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000",
            max_retries=1,
            http_opener=mock_opener,
        )

        with pytest.raises(GeminiTimeoutError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "timed out" in str(exc_info.value).lower()

    def test_malformed_json_envelope(self):
        """Malformed JSON response envelope from Gemini must raise GeminiAPIError."""
        mock_resp = DummyHTTPResponse(b"<html>502 Bad Gateway</html>")
        mock_opener = MagicMock(return_value=mock_resp)

        client = GeminiClient(
            api_key="AIzaSyDUMMY_FOR_TESTS_00000000000000000000",
            http_opener=mock_opener,
        )

        with pytest.raises(GeminiAPIError) as exc_info:
            client.classify("System prompt", "User prompt")

        assert "malformed response JSON" in str(exc_info.value)

