"""
Response Cache for CyberScout AI Collection Framework.

Provides fast, in-memory response caching with TTL expiration.
Fully compatible with ephemeral filesystems (Render, Docker).
"""

from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, Optional, Tuple

from src.core.logging import get_logger

logger = get_logger(__name__)


class CollectorCache:
    """
    In-memory HTTP response cache with TTL expiration.
    """

    def __init__(self, db_path: Optional[Any] = None, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[int, str, datetime]] = {}

    def _hash_url(self, url: str) -> str:
        """Generates SHA256 hash string for a target URL."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def get(self, url: str) -> Optional[Tuple[int, str]]:
        """
        Retrieves cached (status_code, content) tuple if valid and unexpired.

        Args:
            url: Target URL string.

        Returns:
            Tuple of (status_code, content_str) if hit, None if miss or expired.
        """
        url_hash = self._hash_url(url)
        entry = self._cache.get(url_hash)
        if not entry:
            return None

        status_code, content, cached_at = entry
        now = datetime.now(timezone.utc)

        if (now - cached_at).total_seconds() > self.ttl_seconds:
            # Expired
            self._cache.pop(url_hash, None)
            return None

        logger.debug(f"Cache hit for URL '{url}'.")
        return status_code, content

    def set(self, url: str, status_code: int, content: str) -> None:
        """
        Stores response content in cache.

        Args:
            url: Target URL string.
            status_code: HTTP response status code.
            content: Raw response text content.
        """
        url_hash = self._hash_url(url)
        now = datetime.now(timezone.utc)
        self._cache[url_hash] = (status_code, content, now)
        logger.debug(f"Cached response for URL '{url}'.")

    def clear(self) -> None:
        """Clears all cached items."""
        self._cache.clear()

    def count(self) -> int:
        """Returns total number of cached entries."""
        return len(self._cache)
