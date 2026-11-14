"""
Google Gemini API Fallback Client for CyberScout AI Classification (Phase D).

Provides resilient access to Google Gemini GenerateContent API (v1beta) as the
authoritative fallback provider when Groq fails, times out, or returns unusable output.
Enforces identical schema expectations, exponential backoff, jitter, and secret masking.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import random
import re
import socket
import time
from typing import Any, Callable, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from src.core.logging import get_logger
from src.discovery.classification_models import AIProviderMetrics, ClassificationBudget

logger = get_logger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def sanitize_gemini_secret(text: str) -> str:
    """Masks Google API keys (AIza...) and headers to prevent exposure in logs or exceptions."""
    if not text:
        return ""
    # Mask standard Google API keys (AIzaSy...)
    masked = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "AIza[REDACTED]", text)
    # Mask x-goog-api-key headers
    masked = re.sub(r"x-goog-api-key:\s*[^\s]+", "x-goog-api-key: [REDACTED]", masked, flags=re.IGNORECASE)
    raw_key = os.getenv("GEMINI_API_KEY")
    if raw_key and len(raw_key) > 5 and raw_key in masked:
        masked = masked.replace(raw_key, "[REDACTED]")
    return masked


class GeminiError(Exception):
    """Base exception for all Gemini client failures."""

    def __init__(self, message: str, status_code: Optional[int] = None, original_error: Optional[Exception] = None):
        clean_msg = sanitize_gemini_secret(message)
        super().__init__(clean_msg)
        self.message = clean_msg
        self.status_code = status_code
        self.original_error = original_error


class GeminiAuthError(GeminiError):
    """Authentication or authorization failure (HTTP 400/401/403)."""
    pass


class GeminiRateLimitError(GeminiError):
    """Rate limit or RESOURCE_EXHAUSTED (HTTP 429)."""
    pass


class GeminiQuotaError(GeminiError):
    """Daily/monthly quota limit exhausted."""
    pass


class GeminiTimeoutError(GeminiError):
    """Network connection, DNS, or read timeout."""
    pass


class GeminiAPIError(GeminiError):
    """Server-side or unhandled HTTP status error (5xx or unexpected 4xx)."""
    pass


class GeminiClient:
    """
    Fallback AI classification client connecting to Google Gemini GenerateContent API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        backoff_factor: float = 1.5,
        budget: Optional[ClassificationBudget] = None,
        enabled: Optional[bool] = None,
        http_opener: Optional[Callable[..., Any]] = None,
    ):
        if api_key is not None:
            self._api_key = api_key.strip()
        else:
            self._api_key = (os.getenv("GEMINI_API_KEY") or "").strip()

        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.api_url_override = api_url or os.getenv("GEMINI_API_URL")
        self.budget = budget or ClassificationBudget()
        self.timeout = timeout or float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", str(self.budget.timeout_seconds)))
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        env_enabled = os.getenv("AI_CLASSIFICATION_ENABLED", "true").lower() in ("true", "1", "yes")
        self.is_enabled = enabled if enabled is not None else env_enabled

        self._http_opener = http_opener or urllib.request.urlopen
        self.metrics = AIProviderMetrics(provider_name="gemini")
        self.requests_executed_this_run = 0

    @property
    def is_configured(self) -> bool:
        """Returns True if a non-empty API key is present."""
        return bool(self._api_key and len(self._api_key) > 5)

    def _get_endpoint_url(self, model_name: str) -> str:
        if self.api_url_override:
            return self.api_url_override
        return GEMINI_ENDPOINT_TEMPLATE.format(model=model_name)

    def classify(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes Google Gemini generation request with structured JSON mime type.

        Args:
            system_prompt: Authoritative classification instructions.
            user_prompt: Target opportunity content and metadata.
            model: Optional model identifier override.
            temperature: Sampling temperature (default 0.1).
            max_tokens: Maximum output tokens.

        Returns:
            Parsed JSON dictionary returned by Gemini.

        Raises:
            GeminiAuthError: If API key is missing or invalid.
            GeminiRateLimitError: If rate limit / quota exceeded after retries.
            GeminiTimeoutError: On socket/read timeout.
            GeminiAPIError: On unexpected HTTP status or malformed JSON.
        """
        if not self.is_enabled:
            logger.debug("[GeminiClient] Classification skipped: AI classification is disabled via configuration.")
            raise GeminiAPIError("AI classification is disabled via configuration.")

        if not self.is_configured:
            err = "GEMINI_API_KEY is not configured. Fallback classification cannot proceed."
            logger.warning(f"[GeminiClient] {err}")
            self.metrics.record_failure(err)
            raise GeminiAuthError(err, status_code=401)

        active_model = model or self.model
        tokens_limit = max_tokens or self.budget.max_tokens
        endpoint = self._get_endpoint_url(active_model)

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": tokens_limit,
                "responseMimeType": "application/json",
            },
        }

        # Use header authentication rather than URL query parameters to avoid key exposure in proxy logs
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CyberScoutAI-Classifier-Gemini/2.0",
        }

        json_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=json_bytes, headers=headers, method="POST")

        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            start_time = time.time()
            try:
                with self._http_opener(req, timeout=self.timeout) as resp:
                    latency = (time.time() - start_time) * 1000.0
                    body = resp.read().decode("utf-8", errors="replace")

                    try:
                        raw_data = json.loads(body)
                    except json.JSONDecodeError as jde:
                        self.metrics.record_failure(f"Malformed JSON envelope from Gemini: {jde}")
                        raise GeminiAPIError(f"Gemini API returned malformed response JSON: {jde}")

                    # Extract usage metadata
                    usage = raw_data.get("usageMetadata", {})
                    prompt_tokens = usage.get("promptTokenCount", 0)
                    comp_tokens = usage.get("candidatesTokenCount", 0)

                    # Extract candidate parts
                    candidates = raw_data.get("candidates", [])
                    if not candidates:
                        err_msg = "Gemini response contained no candidate parts."
                        self.metrics.record_failure(err_msg)
                        raise GeminiAPIError(err_msg)

                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        err_msg = "Gemini response candidate contained no text parts."
                        self.metrics.record_failure(err_msg)
                        raise GeminiAPIError(err_msg)

                    content_str = parts[0].get("text", "")
                    if not content_str:
                        err_msg = "Gemini returned empty text in candidate content."
                        self.metrics.record_failure(err_msg)
                        raise GeminiAPIError(err_msg)

                    try:
                        parsed_content = json.loads(content_str)
                    except json.JSONDecodeError as jde:
                        self.metrics.record_failure(f"Gemini content text was not valid JSON: {jde}")
                        raise GeminiAPIError(f"Gemini content could not be parsed as JSON: {jde}")

                    self.requests_executed_this_run += 1
                    self.metrics.record_success(latency, prompt_tokens, comp_tokens)
                    logger.debug(f"[GeminiClient] Fallback classification successful using '{active_model}' ({latency:.1f}ms)")
                    return parsed_content

            except urllib.error.HTTPError as http_err:
                latency = (time.time() - start_time) * 1000.0
                status_code = http_err.code
                err_text = ""
                try:
                    err_text = http_err.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass

                clean_err = sanitize_gemini_secret(err_text)
                logger.warning(f"[GeminiClient] HTTP {status_code} on attempt {attempt}/{self.max_retries + 1}: {clean_err}")

                if status_code in (400, 401, 403):
                    self.metrics.record_failure(f"Auth error (HTTP {status_code}): {clean_err}")
                    raise GeminiAuthError(f"Gemini authentication failed (HTTP {status_code}): {clean_err}", status_code=status_code)

                if status_code == 429 or "RESOURCE_EXHAUSTED" in clean_err:
                    self.metrics.record_failure("Rate limited / Resource exhausted (HTTP 429)", is_rate_limit=True)
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                        logger.info(f"[GeminiClient] Rate limit hit. Backing off for {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise GeminiRateLimitError(f"Gemini rate limit exceeded after {self.max_retries} retries", status_code=429)

                if status_code in (408, 500, 502, 503, 504):
                    self.metrics.record_failure(f"Server error (HTTP {status_code})")
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 0.8)
                        logger.info(f"[GeminiClient] Transient HTTP {status_code}. Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise GeminiAPIError(f"Gemini server error HTTP {status_code} after retries: {clean_err}", status_code=status_code)

                self.metrics.record_failure(f"Client error HTTP {status_code}: {clean_err}")
                raise GeminiAPIError(f"Gemini request rejected with HTTP {status_code}: {clean_err}", status_code=status_code)

            except (urllib.error.URLError, TimeoutError, socket.timeout) as conn_err:
                latency = (time.time() - start_time) * 1000.0
                err_str = sanitize_gemini_secret(str(conn_err))
                logger.warning(f"[GeminiClient] Connection/timeout error on attempt {attempt}/{self.max_retries + 1}: {err_str}")

                if attempt <= self.max_retries:
                    sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 0.7)
                    time.sleep(sleep_time)
                    continue
                self.metrics.record_failure(f"Timeout/Connection failure: {err_str}")
                raise GeminiTimeoutError(f"Gemini connection timed out after {self.max_retries} retries: {err_str}", original_error=conn_err)

        raise GeminiAPIError("Gemini classification failed: retry loop exhausted unexpectedly.")
