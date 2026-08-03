"""
SQLite Response Cache for CyberScout AI Collection Framework.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from typing import Optional, Tuple

from src.core.constants import DATA_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class CollectorCache:
    """
    Local SQLite-backed HTTP response cache with TTL expiration.
    """

    def __init__(self, db_path: Optional[Path] = None, ttl_seconds: int = 3600):
        self.db_path = db_path or (DATA_DIR / "collector_cache.db")
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection."""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        """Initializes cache table schema."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS response_cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    cached_at TIMESTAMP NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

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
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status_code, content, cached_at FROM response_cache WHERE url_hash = ?",
                (url_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            status_code, content, cached_at_str = row
            cached_at = datetime.fromisoformat(cached_at_str)
            now = datetime.now(timezone.utc)

            if (now - cached_at).total_seconds() > self.ttl_seconds:
                # Expired
                cursor.execute("DELETE FROM response_cache WHERE url_hash = ?", (url_hash,))
                conn.commit()
                return None

            logger.debug(f"Cache hit for URL '{url}'.")
            return status_code, content
        except Exception as e:
            logger.warning(f"Cache read error for '{url}': {e}")
            return None
        finally:
            conn.close()

    def set(self, url: str, status_code: int, content: str) -> None:
        """
        Stores response content in cache.

        Args:
            url: Target URL string.
            status_code: HTTP response status code.
            content: Raw response text content.
        """
        url_hash = self._hash_url(url)
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO response_cache (url_hash, url, content, status_code, cached_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    content = excluded.content,
                    status_code = excluded.status_code,
                    cached_at = excluded.cached_at;
                """,
                (url_hash, url, content, status_code, now_str),
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"Cache write error for '{url}': {e}")
        finally:
            conn.close()
