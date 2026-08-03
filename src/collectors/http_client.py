"""
Reusable HTTP Client for CyberScout AI Collection Framework.

Uses urllib.request (with requests fallback) with connection pooling, User-Agent rotation,
timeout handling, caching, rate limiting, and retries.
"""

import gzip
from io import BytesIO
from pathlib import Path
import random
import time

from typing import Any, Dict, Optional, Tuple
import urllib.parse
import urllib.request
import yaml

from src.collectors.cache import CollectorCache
from src.collectors.exceptions import HTTPClientError
from src.collectors.metrics import CollectorMetrics
from src.collectors.rate_limiter import RateLimiter
from src.collectors.retry import CollectorRetry
from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class HTTPClient:
    """
    Centralized HTTP Client for all CyberScout AI collectors.
    """

    def __init__(
        self,
        config_file: Optional[Path] = None,
        cache: Optional[CollectorCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        retry_policy: Optional[CollectorRetry] = None,
    ):
        self.config_file = config_file or (CONFIG_DIR / "http.yaml")
        self.user_agents_file = CONFIG_DIR / "user_agents.yaml"

        self.timeout_seconds = 15.0
        self.verify_ssl = True
        self.follow_redirects = True
        self.user_agents = [
            "CyberScoutAI/0.3.0 (+https://github.com/CyberScoutAI/cyberscout-ai)"
        ]

        self.cache = cache or CollectorCache()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_policy = retry_policy or CollectorRetry()

        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads HTTP and User-Agent configurations."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                self.timeout_seconds = float(cfg.get("timeout_seconds", 15.0))
                self.verify_ssl = bool(cfg.get("verify_ssl", True))
                self.follow_redirects = bool(cfg.get("follow_redirects", True))
            except Exception as e:
                logger.warning(f"Could not load http.yaml: {e}")

        if self.user_agents_file.exists():
            try:
                with open(self.user_agents_file, "r", encoding="utf-8") as f:
                    ua_cfg = yaml.safe_load(f) or {}
                    agents = ua_cfg.get("user_agents", [])
                    if isinstance(agents, list) and agents:
                        self.user_agents = agents
            except Exception as e:
                logger.warning(f"Could not load user_agents.yaml: {e}")

    def _get_random_user_agent(self) -> str:
        """Returns a random User-Agent header string."""
        return random.choice(self.user_agents)

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        source_id: Optional[str] = None,
        use_cache: bool = True,
        metrics: Optional[CollectorMetrics] = None,
    ) -> Tuple[int, str]:
        """
        Executes HTTP GET request with caching, rate limiting, and retries.

        Args:
            url: Target URL string.
            params: Query parameters dictionary.
            headers: Custom request headers.
            source_id: Optional source identifier for rate limiting.
            use_cache: Whether to attempt response cache lookup.
            metrics: Optional CollectorMetrics object to update.

        Returns:
            Tuple of (status_code, content_text).
        """
        # Append query params to URL if provided
        target_url = url
        if params:
            encoded_params = urllib.parse.urlencode(params)
            delimiter = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{delimiter}{encoded_params}"

        # 1. Check response cache
        if use_cache and self.cache:
            cached_res = self.cache.get(target_url)
            if cached_res:
                status, text = cached_res
                if metrics:
                    metrics.record_request(success=True, latency=0.0, num_bytes=len(text.encode("utf-8")))
                return status, text

        # 2. Enforce rate limit throttling
        self.rate_limiter.wait(source_id=source_id, url=target_url)

        req_headers = {
            "User-Agent": self._get_random_user_agent(),
            "Accept-Encoding": "gzip, deflate",
        }
        if headers:
            req_headers.update(headers)

        start_time = time.time()

        def _do_get():
            req = urllib.request.Request(target_url, headers=req_headers, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                status_code = response.getcode()
                raw_bytes = response.read()

                # Check gzip encoding
                if response.headers.get("Content-Encoding") == "gzip":
                    buf = BytesIO(raw_bytes)
                    with gzip.GzipFile(fileobj=buf) as f:
                        raw_bytes = f.read()

                content_text = raw_bytes.decode("utf-8", errors="replace")
                return status_code, content_text

        try:
            status_code, text = self.retry_policy.execute(_do_get)
            latency = time.time() - start_time

            if metrics:
                metrics.record_request(success=True, latency=latency, num_bytes=len(text.encode("utf-8")))

            # Cache successful GET response
            if use_cache and self.cache and status_code == 200:
                self.cache.set(target_url, status_code, text)

            logger.info(f"HTTP GET '{target_url}' succeeded [{status_code}] in {latency:.2f}s.")
            return status_code, text

        except Exception as e:
            latency = time.time() - start_time
            if metrics:
                metrics.record_request(success=False, latency=latency, num_bytes=0)
            logger.error(f"HTTP GET '{target_url}' failed: {e}")
            raise HTTPClientError(f"HTTP GET request to '{target_url}' failed: {e}", original_exception=e)
