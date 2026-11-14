"""
Groq API Primary Client for CyberScout AI Classification (Phase D).

Provides resilient, budgeted access to Groq Chat Completions API with
exponential backoff, jitter, secret masking, JSON object response enforcement,
and usage telemetry tracking.
"""

from dataclasses import dataclass, field
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

DEFAULT_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


def sanitize_groq_secret(text: str) -> str:
    """Masks Groq API keys (gsk_...) and Bearer tokens to prevent leakage in logs or exceptions."""
    if not text:
        return ""
    # Mask Groq API keys (gsk_...)
    masked = re.sub(r"gsk_[A-Za-z0-9_\-]{20,}", "gsk_[REDACTED]", text)
    # Mask Authorization Bearer headers
    masked = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", masked, flags=re.IGNORECASE)
    raw_key = os.getenv("GROQ_API_KEY")
    if raw_key and len(raw_key) > 5 and raw_key in masked:
        masked = masked.replace(raw_key, "[REDACTED]")
    return masked


class GroqError(Exception):
    """Base exception for all Groq client failures."""

    def __init__(self, message: str, status_code: Optional[int] = None, original_error: Optional[Exception] = None):
        clean_msg = sanitize_groq_secret(message)
        super().__init__(clean_msg)
        self.message = clean_msg
        self.status_code = status_code
        self.original_error = original_error


class GroqAuthError(GroqError):
    """Authentication or authorization failure (HTTP 401/403)."""
    pass


class GroqRateLimitError(GroqError):
    """Rate limit (HTTP 429) exceeded after retry backoff exhausted."""
    pass


class GroqQuotaError(GroqError):
    """Credit or quota limit reached (HTTP 402/insufficient quota)."""
    pass


class GroqTimeoutError(GroqError):
    """Network connection, DNS, or read timeout."""
    pass


class GroqAPIError(GroqError):
    """Server-side or unhandled HTTP status error (5xx or unexpected 4xx)."""
    pass


class GroqClient:
    """
    Primary AI classification client connecting to Groq Chat Completions API.
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
            self._api_key = (os.getenv("GROQ_API_KEY") or "").strip()

        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self.api_url = api_url or os.getenv("GROQ_API_URL", DEFAULT_GROQ_API_URL)
        self.budget = budget or ClassificationBudget()
        self.timeout = timeout or float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", str(self.budget.timeout_seconds)))
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        env_enabled = os.getenv("AI_CLASSIFICATION_ENABLED", "true").lower() in ("true", "1", "yes")
        self.is_enabled = enabled if enabled is not None else env_enabled

        self._http_opener = http_opener or urllib.request.urlopen
        self.metrics = AIProviderMetrics(provider_name="groq")
        self.requests_executed_this_run = 0

    @property
    def is_configured(self) -> bool:
        """Returns True if a non-empty API key is present."""
        return bool(self._api_key and len(self._api_key) > 5)

    def classify(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes chat completion request with JSON object formatting.

        Args:
            system_prompt: Authoritative classification instructions.
            user_prompt: Target opportunity content and metadata.
            model: Optional model identifier override.
            temperature: Sampling temperature (default 0.1 for deterministic classification).
            max_tokens: Maximum completion tokens.

        Returns:
            Parsed JSON dictionary returned by the model.

        Raises:
            GroqAuthError: If API key is missing or invalid.
            GroqRateLimitError: If HTTP 429 persists after retries.
            GroqQuotaError: If quota exhausted.
            GroqTimeoutError: On socket/read timeout.
            GroqAPIError: On unexpected HTTP status or malformed JSON.
        """
        if not self.is_enabled:
            logger.debug("[GroqClient] Classification skipped: AI classification is disabled via configuration.")
            raise GroqAPIError("AI classification is disabled via configuration.")

        if not self.is_configured:
            err = "GROQ_API_KEY is not configured. Classification cannot proceed."
            logger.warning(f"[GroqClient] {err}")
            self.metrics.record_failure(err)
            raise GroqAuthError(err, status_code=401)

        active_model = model or self.model
        tokens_limit = max_tokens or self.budget.max_tokens

        payload = {
            "model": active_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": tokens_limit,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CyberScoutAI-Classifier/2.0",
        }

        json_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=json_bytes, headers=headers, method="POST")

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
                        self.metrics.record_failure(f"Malformed JSON from Groq: {jde}")
                        raise GroqAPIError(f"Groq API returned malformed response JSON: {jde}")

                    # Extract usage metadata
                    usage = raw_data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    comp_tokens = usage.get("completion_tokens", 0)

                    # Extract content
                    choices = raw_data.get("choices", [])
                    if not choices:
                        err_msg = "Groq response contained no completion choices."
                        self.metrics.record_failure(err_msg)
                        raise GroqAPIError(err_msg)

                    content_str = choices[0].get("message", {}).get("content", "")
                    if not content_str:
                        err_msg = "Groq response returned empty message content."
                        self.metrics.record_failure(err_msg)
                        raise GroqAPIError(err_msg)

                    try:
                        parsed_content = json.loads(content_str)
                    except json.JSONDecodeError as jde:
                        self.metrics.record_failure(f"Groq content was not valid JSON: {jde}")
                        raise GroqAPIError(f"Groq completion content could not be parsed as JSON: {jde}")

                    self.requests_executed_this_run += 1
                    self.metrics.record_success(latency, prompt_tokens, comp_tokens)
                    logger.debug(f"[GroqClient] Classification successful using '{active_model}' ({latency:.1f}ms)")
                    return parsed_content

            except urllib.error.HTTPError as http_err:
                latency = (time.time() - start_time) * 1000.0
                status_code = http_err.code
                err_text = ""
                try:
                    err_text = http_err.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass

                clean_err = sanitize_groq_secret(err_text)
                logger.warning(f"[GroqClient] HTTP {status_code} on attempt {attempt}/{self.max_retries + 1}: {clean_err}")

                if status_code in (401, 403):
                    self.metrics.record_failure(f"Auth error (HTTP {status_code}): {clean_err}")
                    raise GroqAuthError(f"Groq authentication failed (HTTP {status_code}): {clean_err}", status_code=status_code)

                if status_code == 402 or "insufficient_quota" in clean_err.lower():
                    self.metrics.record_failure(f"Quota error (HTTP {status_code}): {clean_err}")
                    raise GroqQuotaError(f"Groq quota or credit limit exhausted: {clean_err}", status_code=status_code)

                if status_code == 429:
                    self.metrics.record_failure("Rate limited (HTTP 429)", is_rate_limit=True)
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                        logger.info(f"[GroqClient] Rate limit hit. Backing off for {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise GroqRateLimitError(f"Groq rate limit exceeded after {self.max_retries} retries", status_code=429)

                if status_code in (408, 500, 502, 503, 504):
                    self.metrics.record_failure(f"Server error (HTTP {status_code})")
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 0.8)
                        logger.info(f"[GroqClient] Transient HTTP {status_code}. Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise GroqAPIError(f"Groq server error HTTP {status_code} after retries: {clean_err}", status_code=status_code)

                self.metrics.record_failure(f"Client error HTTP {status_code}: {clean_err}")
                raise GroqAPIError(f"Groq request rejected with HTTP {status_code}: {clean_err}", status_code=status_code)

            except (urllib.error.URLError, TimeoutError, socket.timeout) as conn_err:
                latency = (time.time() - start_time) * 1000.0
                err_str = sanitize_groq_secret(str(conn_err))
                logger.warning(f"[GroqClient] Connection/timeout error on attempt {attempt}/{self.max_retries + 1}: {err_str}")

                if attempt <= self.max_retries:
                    sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 0.7)
                    time.sleep(sleep_time)
                    continue
                self.metrics.record_failure(f"Timeout/Connection failure: {err_str}")
                raise GroqTimeoutError(f"Groq connection timed out after {self.max_retries} retries: {err_str}", original_error=conn_err)

        raise GroqAPIError("Groq classification failed: retry loop exhausted unexpectedly.")

