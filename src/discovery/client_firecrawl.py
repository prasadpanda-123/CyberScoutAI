"""
Firecrawl Scrape API Client for CyberScout AI.

Provides resilient, budgeted, rate-limited access to Firecrawl Scrape API (v1)
with exponential backoff, jitter, secret masking, and health telemetry.
Used exclusively in Phase C for extracting content from candidate URLs
discovered by Tavily. Does not perform search or discovery.
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
from src.discovery.discovery_models import ExtractionBudget
from src.discovery.url_validator import URLValidator

logger = get_logger(__name__)

DEFAULT_FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"


def sanitize_firecrawl_secret(text: str) -> str:
    """
    Masks Firecrawl API tokens and Authorization headers to prevent leakage in logs or exceptions.
    """
    if not text:
        return ""
    # Mask Firecrawl API keys (fc-...)
    masked = re.sub(r"fc-[A-Za-z0-9_\-]{16,}", "fc-[REDACTED]", text)
    # Mask Authorization Bearer headers
    masked = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", masked, flags=re.IGNORECASE)
    # Mask raw environment key if set
    raw_key = os.getenv("FIRECRAWL_API_KEY")
    if raw_key and len(raw_key) > 5 and raw_key in masked:
        masked = masked.replace(raw_key, "[REDACTED]")
    return masked


# Exception hierarchy
class FirecrawlError(Exception):
    """Base exception for all Firecrawl scraping errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, original_error: Optional[Exception] = None):
        clean_msg = sanitize_firecrawl_secret(message)
        super().__init__(clean_msg)
        self.message = clean_msg
        self.status_code = status_code
        self.original_error = original_error


class FirecrawlAuthError(FirecrawlError):
    """Authentication or authorization failure (HTTP 401/403)."""
    pass


class FirecrawlRateLimitError(FirecrawlError):
    """Rate limit exceeded (HTTP 429) after retry budget exhausted."""
    pass


class FirecrawlBudgetExceededError(FirecrawlError):
    """Scrape operation blocked due to daily or run budget exhaustion."""
    pass


class FirecrawlTimeoutError(FirecrawlError):
    """Network connection, DNS, or read timeout during scrape."""
    pass


class FirecrawlSecurityError(FirecrawlError):
    """Target or redirect URL rejected due to SSRF or dangerous scheme."""
    pass


class FirecrawlAPIError(FirecrawlError):
    """Server-side or unhandled HTTP status error (5xx or unexpected 4xx)."""
    pass


@dataclass
class FirecrawlClientMetrics:
    """Telemetry tracking execution performance and error classifications."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limits_encountered: int = 0
    total_latency_ms: float = 0.0
    last_request_at: Optional[str] = None
    last_error: Optional[str] = None

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return round(self.total_latency_ms / self.successful_requests, 2)

    def record_success(self, latency_ms: float) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.last_request_at = datetime.now(timezone.utc).isoformat()

    def record_failure(self, error_msg: str, is_rate_limit: bool = False) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        if is_rate_limit:
            self.rate_limits_encountered += 1
        self.last_error = sanitize_firecrawl_secret(error_msg)
        self.last_request_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limits_encountered": self.rate_limits_encountered,
            "avg_latency_ms": self.avg_latency_ms,
            "last_request_at": self.last_request_at,
            "last_error": self.last_error,
        }


class FirecrawlClient:
    """
    HTTP client for the Firecrawl Scrape API.
    
    Provides bounded retries with exponential backoff + jitter,
    SSRF validation gating, request timeouts, rate limits, and sanitized logging.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        budget: Optional[ExtractionBudget] = None,
        enabled: Optional[bool] = None,
        http_opener: Optional[Callable[..., Any]] = None,
        url_validator: Optional[URLValidator] = None,
    ):
        if api_key is not None:
            self._api_key = api_key.strip()
        else:
            self._api_key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()

        self.api_url = api_url or os.getenv("FIRECRAWL_API_URL", DEFAULT_FIRECRAWL_API_URL)
        self.budget = budget or ExtractionBudget()
        self.timeout = timeout or float(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", str(self.budget.timeout_seconds)))
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Firecrawl fetches targets from its own network. Require an explicit
        # production opt-in so provider redirect and egress controls can be
        # configured before untrusted discovered URLs are sent to it.
        runtime_env = (os.getenv("CYBERSCOUT_ENV") or os.getenv("APP_ENV") or "production").lower()
        default_enabled = runtime_env not in ("production", "prod")
        env_enabled = os.getenv("FIRECRAWL_ENABLED", str(default_enabled)).lower() in ("true", "1", "yes")
        self.is_enabled = enabled if enabled is not None else env_enabled

        # Optional test hook for mocking urlopen without touching the network
        self._http_opener = http_opener or urllib.request.urlopen
        self.url_validator = url_validator or URLValidator(resolve_dns=True)

        self.metrics = FirecrawlClientMetrics()
        self.daily_requests_executed = 0
        self.run_requests_executed = 0
        self._last_request_timestamp: float = 0.0

    @property
    def is_configured(self) -> bool:
        """Returns True if a non-empty API key is available."""
        return bool(self._api_key and len(self._api_key) > 5)

    def _apply_rate_limiting(self) -> None:
        """Enforces client-side rate limiting to stay within safe RPM bounds."""
        if self.budget.rate_limit_rpm <= 0:
            return
        min_interval = 60.0 / self.budget.rate_limit_rpm
        elapsed = time.time() - self._last_request_timestamp
        if elapsed < min_interval:
            sleep_needed = min_interval - elapsed
            time.sleep(sleep_needed)
        self._last_request_timestamp = time.time()

    def scrape_url(
        self,
        url: str,
        formats: Optional[List[str]] = None,
        only_main_content: bool = True,
        wait_for_ms: int = 1000,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Submits target URL to Firecrawl /v1/scrape and returns structured markdown and metadata.

        Args:
            url: Validated HTTP/HTTPS web address to scrape.
            formats: Desired extraction formats (e.g. ['markdown', 'html']). Defaults to ['markdown', 'html'].
            only_main_content: If True, strips navigation, headers, footers for cleaner extraction.
            wait_for_ms: JavaScript rendering wait time in milliseconds.
            timeout: Optional per-request timeout override.

        Returns:
            Dictionary containing 'markdown', 'html', and 'metadata'.

        Raises:
            FirecrawlAuthError: If API key is missing or rejected by Firecrawl.
            FirecrawlRateLimitError: If rate limit (429) persists beyond retries.
            FirecrawlBudgetExceededError: If daily or run budget limit reached.
            FirecrawlTimeoutError: On network or server timeout.
            FirecrawlAPIError: On unexpected 4xx/5xx responses.
        """
        if not self.is_enabled:
            logger.debug("[FirecrawlClient] Scrape skipped: Firecrawl is disabled via configuration.")
            return {"markdown": "", "html": "", "metadata": {"error": "Firecrawl disabled"}}

        validation = self.url_validator.validate(url)
        if not validation.is_valid:
            reason = validation.rejection_reason or "Target URL failed security validation"
            self.metrics.record_failure(f"Unsafe scrape target rejected: {reason}")
            raise FirecrawlSecurityError(f"Unsafe scrape target rejected: {reason}")

        if not self.is_configured:
            err = "FIRECRAWL_API_KEY is not configured. Scrape cannot proceed."
            logger.warning(f"[FirecrawlClient] {err}")
            self.metrics.record_failure(err)
            raise FirecrawlAuthError(err, status_code=401)

        # Enforce run budget
        if self.run_requests_executed >= self.budget.max_pages_per_run:
            err = f"Firecrawl run budget exceeded ({self.run_requests_executed}/{self.budget.max_pages_per_run} pages)."
            logger.warning(f"[FirecrawlClient] {err}")
            self.metrics.record_failure(err)
            raise FirecrawlBudgetExceededError(err)

        # Enforce daily budget
        if self.daily_requests_executed >= self.budget.daily_limit:
            err = f"Firecrawl daily budget exceeded ({self.daily_requests_executed}/{self.budget.daily_limit} pages)."
            logger.warning(f"[FirecrawlClient] {err}")
            self.metrics.record_failure(err)
            raise FirecrawlBudgetExceededError(err)

        self._apply_rate_limiting()

        req_timeout = timeout or self.timeout
        target_formats = formats or ["markdown", "html"]

        payload = {
            "url": url.strip(),
            "formats": target_formats,
            "onlyMainContent": only_main_content,
            "waitFor": wait_for_ms,
            "timeout": int(req_timeout * 1000),
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CyberScoutAI-Extractor/2.0",
        }

        json_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.api_url, data=json_bytes, headers=headers, method="POST")

        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            start_time = time.time()
            try:
                with self._http_opener(req, timeout=req_timeout) as resp:
                    latency = (time.time() - start_time) * 1000.0
                    body = resp.read(self.budget.max_response_size + 1)
                    if len(body) > self.budget.max_response_size:
                        self.metrics.record_failure("Firecrawl response exceeded the configured size limit")
                        raise FirecrawlAPIError("Firecrawl response exceeded the configured size limit")

                    body_str = body.decode("utf-8", errors="replace")
                    try:
                        data = json.loads(body_str)
                    except json.JSONDecodeError as jde:
                        self.metrics.record_failure(f"Malformed JSON from Firecrawl: {jde}")
                        raise FirecrawlAPIError(f"Firecrawl returned malformed JSON: {jde}")

                    # Check success envelope
                    if not data.get("success", False) and "data" not in data:
                        err_msg = data.get("error") or "Unknown Firecrawl error"
                        self.metrics.record_failure(f"Firecrawl API reported failure: {err_msg}")
                        raise FirecrawlAPIError(f"Firecrawl scrape failed: {err_msg}")

                    scrape_data = data.get("data") or {}
                    self.daily_requests_executed += 1
                    self.run_requests_executed += 1
                    self.metrics.record_success(latency)
                    logger.debug(f"[FirecrawlClient] Scraped successfully: '{sanitize_firecrawl_secret(url[:50])}' ({latency:.1f}ms)")
                    return scrape_data

            except urllib.error.HTTPError as http_err:
                latency = (time.time() - start_time) * 1000.0
                status_code = http_err.code
                err_text = ""
                try:
                    err_text = http_err.read(self.budget.max_response_size + 1).decode("utf-8", errors="ignore")
                except Exception:
                    pass

                clean_err = sanitize_firecrawl_secret(err_text)
                logger.warning(f"[FirecrawlClient] HTTP {status_code} on attempt {attempt}/{self.max_retries + 1}: {clean_err}")

                if status_code in (401, 403):
                    self.metrics.record_failure(f"Auth error (HTTP {status_code}): {clean_err}")
                    raise FirecrawlAuthError(f"Firecrawl auth failed (HTTP {status_code}): {clean_err}", status_code=status_code)

                if status_code == 402:
                    self.metrics.record_failure(f"Quota exceeded (HTTP 402): {clean_err}")
                    raise FirecrawlBudgetExceededError(f"Firecrawl credit limit reached: {clean_err}", status_code=402)

                if status_code == 429:
                    self.metrics.record_failure("Rate limited (HTTP 429)", is_rate_limit=True)
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                        logger.info(f"[FirecrawlClient] Rate limit hit. Backing off for {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise FirecrawlRateLimitError(f"Firecrawl rate limit exceeded after {self.max_retries} retries", status_code=429)

                # Transient server errors (500, 502, 503, 504) or gateway timeout (408)
                if status_code in (408, 500, 502, 503, 504):
                    self.metrics.record_failure(f"Server error (HTTP {status_code})")
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 0.9)
                        logger.info(f"[FirecrawlClient] Transient server error HTTP {status_code}. Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise FirecrawlAPIError(f"Firecrawl server error HTTP {status_code} after retries: {clean_err}", status_code=status_code)

                # Non-retryable client errors (400, 404, etc.)
                self.metrics.record_failure(f"Client error HTTP {status_code}: {clean_err}")
                raise FirecrawlAPIError(f"Firecrawl request rejected with HTTP {status_code}: {clean_err}", status_code=status_code)

            except (urllib.error.URLError, TimeoutError, socket.timeout) as conn_err:
                latency = (time.time() - start_time) * 1000.0
                err_str = sanitize_firecrawl_secret(str(conn_err))
                logger.warning(f"[FirecrawlClient] Connection timeout/error on attempt {attempt}/{self.max_retries + 1}: {err_str}")

                if attempt <= self.max_retries:
                    sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 0.7)
                    time.sleep(sleep_time)
                    continue
                self.metrics.record_failure(f"Timeout/Connection failure: {err_str}")
                raise FirecrawlTimeoutError(f"Firecrawl connection failed after {self.max_retries} retries: {err_str}", original_error=conn_err)

        raise FirecrawlAPIError("Firecrawl scrape failed: maximum retry loop exited unexpectedly.")

