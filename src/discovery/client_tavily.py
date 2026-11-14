"""
Tavily Search API Client for CyberScout AI.

Provides resilient, budgeted, rate-limited access to Tavily Global Search API
with exponential backoff, retry handling, secret masking, and health telemetry.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import random
import re
import socket
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from src.core.logging import get_logger
from src.discovery.discovery_models import DiscoveryBudget, SearchQuerySpec

logger = get_logger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def sanitize_secret(text: str) -> str:
    """
    Masks Tavily and other authorization tokens to prevent leakage in logs or exceptions.
    """
    if not text:
        return ""
    # Mask Tavily API keys (tvly-...)
    masked = re.sub(r"tvly-[A-Za-z0-9_\-]{16,}", "tvly-[REDACTED]", text)
    # Mask Authorization headers
    masked = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", masked, flags=re.IGNORECASE)
    # Mask raw environment key if set
    raw_key = os.getenv("TAVILY_API_KEY")
    if raw_key and len(raw_key) > 5 and raw_key in masked:
        masked = masked.replace(raw_key, "[REDACTED]")
    return masked


class TavilyAPIError(Exception):
    """Base exception for Tavily API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, original_error: Optional[Exception] = None):
        clean_msg = sanitize_secret(message)
        super().__init__(clean_msg)
        self.status_code = status_code
        self.original_error = original_error


class TavilyAuthError(TavilyAPIError):
    """Raised when Tavily API key is missing or unauthorized (HTTP 401/403)."""
    pass


class TavilyRateLimitError(TavilyAPIError):
    """Raised when Tavily rate limits are exceeded (HTTP 429)."""
    pass


class TavilyTimeoutError(TavilyAPIError):
    """Raised when Tavily request times out."""
    pass


class TavilyBudgetExceededError(TavilyAPIError):
    """Raised when configured search budget limit has been reached."""
    pass


@dataclass
class TavilyHealthMetrics:
    """Telemetry tracking provider reliability and latency."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    consecutive_failures: int = 0
    last_latency_ms: float = 0.0
    last_request_time: Optional[str] = None
    last_error: Optional[str] = None
    is_healthy: bool = True

    def record_success(self, latency_ms: float):
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.last_latency_ms = latency_ms
        self.last_request_time = datetime.now(timezone.utc).isoformat()
        self.is_healthy = True

    def record_failure(self, error_msg: str, is_rate_limit: bool = False):
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        if is_rate_limit:
            self.rate_limited_requests += 1
        self.last_error = sanitize_secret(error_msg)
        self.last_request_time = datetime.now(timezone.utc).isoformat()
        if self.consecutive_failures >= 3:
            self.is_healthy = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limited_requests": self.rate_limited_requests,
            "consecutive_failures": self.consecutive_failures,
            "last_latency_ms": round(self.last_latency_ms, 2),
            "last_request_time": self.last_request_time,
            "last_error": self.last_error,
            "is_healthy": self.is_healthy,
        }


class TavilyClient:
    """
    Dedicated client for executing search queries via the Tavily Search API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 25.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        budget: Optional[DiscoveryBudget] = None,
    ):
        if api_key is not None:
            self._api_key = api_key.strip()
        else:
            self._api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.budget = budget or DiscoveryBudget()
        self.metrics = TavilyHealthMetrics()

        # In-memory tracking for budget enforcement in the current process
        self.daily_requests_executed = 0
        self.monthly_requests_executed = 0

    @property
    def is_configured(self) -> bool:
        """Checks if a non-placeholder API key is configured."""
        return bool(self._api_key and not self._api_key.startswith("your_") and len(self._api_key) > 10)

    def search(
        self,
        query: str,
        search_depth: str = "advanced",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        max_results: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Executes search query against Tavily REST API with exponential backoff and error recovery.

        Args:
            query: Natural language or boolean search query string.
            search_depth: 'basic' or 'advanced' (defaults to 'advanced' for deeper opportunity discovery).
            include_domains: Optional list of target domains to restrict search to.
            exclude_domains: Optional list of domains to exclude.
            max_results: Maximum number of search results to return (capped at 20).

        Returns:
            List of raw search result dictionaries containing title, url, content, score.

        Raises:
            TavilyAuthError: If API key is missing or rejected.
            TavilyRateLimitError: If rate limit quota is exceeded after retries.
            TavilyTimeoutError: If all retries time out.
            TavilyBudgetExceededError: If daily/monthly limits are exhausted.
        """
        if not self.is_configured:
            err = "TAVILY_API_KEY is not configured or contains placeholder."
            self.metrics.record_failure(err)
            raise TavilyAuthError(err, status_code=401)

        # Enforce budget guardrails
        if self.daily_requests_executed >= self.budget.daily_limit:
            err = f"Daily discovery search budget reached ({self.budget.daily_limit} searches)."
            logger.warning(err)
            raise TavilyBudgetExceededError(err)

        if self.monthly_requests_executed >= self.budget.monthly_budget:
            err = f"Monthly discovery search budget reached ({self.budget.monthly_budget} searches)."
            logger.warning(err)
            raise TavilyBudgetExceededError(err)

        payload: Dict[str, Any] = {
            "api_key": self._api_key,
            "query": query.strip(),
            "search_depth": search_depth,
            "max_results": min(max_results, self.budget.max_results_per_query),
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        if include_domains:
            payload["include_domains"] = [d.strip() for d in include_domains if d.strip()]
        if exclude_domains:
            payload["exclude_domains"] = [d.strip() for d in exclude_domains if d.strip()]

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CyberScoutAI-Discovery/2.0",
        }

        json_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(TAVILY_SEARCH_URL, data=json_bytes, headers=headers, method="POST")

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.max_retries:
            attempt += 1
            start_time = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    latency = (time.time() - start_time) * 1000.0
                    body = resp.read().decode("utf-8")
                    data = json.loads(body)

                    results = data.get("results", [])
                    self.daily_requests_executed += 1
                    self.monthly_requests_executed += 1
                    self.metrics.record_success(latency)
                    logger.debug(f"Tavily search success: query='{sanitize_secret(query[:40])}' results={len(results)} ({latency:.1f}ms)")
                    return results

            except urllib.error.HTTPError as http_err:
                latency = (time.time() - start_time) * 1000.0
                status_code = http_err.code
                err_text = ""
                try:
                    err_text = http_err.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass

                clean_err_text = sanitize_secret(err_text)
                logger.warning(f"Tavily API HTTP {status_code} (Attempt {attempt}/{self.max_retries + 1}): {clean_err_text}")

                if status_code in (401, 403):
                    self.metrics.record_failure(f"Auth error (HTTP {status_code}): {clean_err_text}")
                    raise TavilyAuthError(f"Tavily authentication failed (HTTP {status_code}): {clean_err_text}", status_code=status_code)

                if status_code == 429:
                    self.metrics.record_failure(f"Rate limited (HTTP 429)", is_rate_limit=True)
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.5, 1.5)
                        logger.info(f"Rate limit hit. Backing off for {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise TavilyRateLimitError(f"Tavily rate limit exceeded after {self.max_retries} retries", status_code=429)

                # Transient server errors (500, 502, 503, 504)
                if status_code in (500, 502, 503, 504):
                    self.metrics.record_failure(f"Server error (HTTP {status_code})")
                    if attempt <= self.max_retries:
                        sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.2, 0.8)
                        logger.info(f"Tavily server error HTTP {status_code}. Retrying in {sleep_time:.2f}s...")
                        time.sleep(sleep_time)
                        continue
                    raise TavilyAPIError(f"Tavily server error HTTP {status_code} after retries: {clean_err_text}", status_code=status_code)

                # Unhandled client error
                self.metrics.record_failure(f"HTTP {status_code}: {clean_err_text}")
                raise TavilyAPIError(f"Tavily API request failed with HTTP {status_code}: {clean_err_text}", status_code=status_code)

            except (urllib.error.URLError, TimeoutError, socket.timeout) as conn_err:
                latency = (time.time() - start_time) * 1000.0
                is_timeout = isinstance(conn_err, (TimeoutError, socket.timeout)) or "timed out" in str(conn_err).lower()
                clean_msg = sanitize_secret(str(conn_err))
                logger.warning(f"Tavily network error (Attempt {attempt}/{self.max_retries + 1}): {clean_msg}")

                if attempt <= self.max_retries:
                    sleep_time = (self.backoff_factor ** attempt) + random.uniform(0.3, 1.0)
                    time.sleep(sleep_time)
                    continue

                if is_timeout:
                    self.metrics.record_failure("Request timed out")
                    raise TavilyTimeoutError(f"Tavily request timed out after {self.timeout}s: {clean_msg}", original_error=conn_err)

                self.metrics.record_failure(f"Connection failed: {clean_msg}")
                raise TavilyAPIError(f"Tavily network error: {clean_msg}", original_error=conn_err)

            except Exception as e:
                self.metrics.record_failure(f"Unexpected error: {str(e)}")
                raise TavilyAPIError(f"Unexpected error during Tavily search: {sanitize_secret(str(e))}", original_error=e)

        raise TavilyAPIError("Tavily search execution exhausted retries without result")

    def execute_query_spec(self, spec: SearchQuerySpec) -> List[Dict[str, Any]]:
        """Executes a structured SearchQuerySpec item."""
        return self.search(
            query=spec.query,
            search_depth=spec.search_depth,
            include_domains=spec.include_domains if spec.include_domains else None,
            exclude_domains=spec.exclude_domains if spec.exclude_domains else None,
            max_results=spec.max_results,
        )
