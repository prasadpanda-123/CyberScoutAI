"""
Reusable HTTP Client for CyberScout AI Collection Framework.

Uses urllib.request with connection pooling, User-Agent rotation,
timeout handling, caching, rate limiting, retries, and secure GitHub API token injection.
"""

import gzip
from io import BytesIO
import os
from pathlib import Path
import random
import re
import time
from typing import Any, Dict, Optional, Tuple
import urllib.error
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

import requests
from requests.adapters import HTTPAdapter

logger = get_logger(__name__)


def sanitize_secret_text(text: str) -> str:
    """
    Sanitizes string to prevent accidental leakage of secrets (e.g. GITHUB_TOKEN).

    Args:
        text: Raw text string.

    Returns:
        Redacted text string.
    """
    if not text:
        return text
    
    # 1. Mask active GITHUB_TOKEN from env
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token and len(github_token) > 4 and github_token != "your_github_personal_access_token":
        text = text.replace(github_token, "[REDACTED]")

    # 2. Mask GitHub Personal Access Tokens (ghp_...)
    text = re.sub(r"ghp_[A-Za-z0-9_]{20,}", "[REDACTED]", text)
    
    # 3. Mask Authorization Bearer headers
    text = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)

    return text


class HTTPClient:
    """
    Centralized HTTP Client for all CyberScout AI collectors with requests.Session pooling.
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

        self.connect_timeout = 10.0
        self.read_timeout = 20.0
        self.timeout = (self.connect_timeout, self.read_timeout)
        self.verify_ssl = True
        self.follow_redirects = True
        self.user_agents = [
            "CyberScoutAI/1.1.2 (+https://github.com/CyberScoutAI/cyberscout-ai)"
        ]

        self.cache = cache or CollectorCache()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.retry_policy = retry_policy or CollectorRetry()

        # Connection Pooling setup via requests.Session
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads HTTP and User-Agent configurations."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                self.connect_timeout = float(cfg.get("connect_timeout", 10.0))
                self.read_timeout = float(cfg.get("read_timeout", 20.0))
                self.timeout = (self.connect_timeout, self.read_timeout)
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
        Executes HTTP GET request with requests connection pooling, timeouts, and logging.

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

        # 3. Secure GitHub Token Integration
        if "api.github.com" in target_url.lower():
            req_headers["Accept"] = "application/vnd.github+json"
            req_headers["X-GitHub-Api-Version"] = "2022-11-28"
            req_headers["User-Agent"] = "CyberScoutAI"

            token = os.getenv("GITHUB_TOKEN")
            if token and token.strip() and token.strip() != "your_github_personal_access_token":
                req_headers["Authorization"] = f"Bearer {token.strip()}"

        if headers:
            req_headers.update(headers)

        start_time = time.time()
        safe_target_url = sanitize_secret_text(target_url)

        def _do_get():
            try:
                resp = self.session.get(
                    target_url,
                    headers=req_headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                    allow_redirects=self.follow_redirects,
                )
                status_code = resp.status_code
                content_text = resp.text
                if status_code == 401:
                    safe_err = sanitize_secret_text(f"HTTP 401 - {resp.reason}")
                    raise HTTPClientError(f"GitHub API 401 Unauthorized: {safe_err}")
                elif status_code == 403:
                    safe_err = sanitize_secret_text(f"HTTP 403 - {resp.reason}")
                    raise HTTPClientError(f"GitHub API 403 Rate Limit Exceeded: {safe_err}")
                elif status_code >= 500:
                    safe_err = sanitize_secret_text(f"HTTP {status_code} Server Error - {resp.reason}")
                    raise HTTPClientError(f"Server Error {status_code}: {safe_err}")
                return status_code, content_text

            except requests.exceptions.ConnectTimeout as conn_err:
                logger.error(f"HTTP GET '{safe_target_url}' failed: ConnectTimeout (host took >{self.connect_timeout}s to connect)")
                raise HTTPClientError(f"ConnectTimeout to '{safe_target_url}' (exceeded {self.connect_timeout}s limit)", original_exception=conn_err)
            except requests.exceptions.ReadTimeout as read_err:
                logger.error(f"HTTP GET '{safe_target_url}' failed: ReadTimeout (server took >{self.read_timeout}s to send data)")
                raise HTTPClientError(f"ReadTimeout from '{safe_target_url}' (exceeded {self.read_timeout}s limit)", original_exception=read_err)
            except requests.exceptions.Timeout as timeout_err:
                logger.error(f"HTTP GET '{safe_target_url}' failed: Timeout")
                raise HTTPClientError(f"Request timeout for '{safe_target_url}'", original_exception=timeout_err)
            except requests.exceptions.RequestException as req_err:
                safe_msg = sanitize_secret_text(str(req_err))
                logger.error(f"HTTP GET '{safe_target_url}' failed: {safe_msg}")
                raise HTTPClientError(f"Connection failed to '{safe_target_url}': {safe_msg}", original_exception=req_err)

        try:
            status_code, text = self.retry_policy.execute(_do_get)
            latency = time.time() - start_time

            if metrics:
                metrics.record_request(success=True, latency=latency, num_bytes=len(text.encode("utf-8")))

            # Cache successful GET response
            if use_cache and self.cache and status_code == 200:
                self.cache.set(target_url, status_code, text)

            safe_url = sanitize_secret_text(target_url)
            logger.info(f"HTTP GET '{safe_url}' succeeded [{status_code}] in {latency:.2f}s.")
            return status_code, text

        except Exception as e:
            latency = time.time() - start_time
            if metrics:
                metrics.record_request(success=False, latency=latency, num_bytes=0)
            safe_err = sanitize_secret_text(str(e))
            safe_url = sanitize_secret_text(target_url)
            logger.error(f"HTTP GET '{safe_url}' failed: {safe_err}")
            raise HTTPClientError(f"HTTP GET request to '{safe_url}' failed: {safe_err}", original_exception=e)
