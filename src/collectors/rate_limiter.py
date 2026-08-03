"""
Rate Limiter for CyberScout AI Collection Framework.
"""

from pathlib import Path
import time
from typing import Any, Dict, Optional
import urllib.parse
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Manages per-domain and per-source request delay throttling.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "rate_limits.yaml")
        self.default_delay: float = 1.0
        self.source_limits: Dict[str, float] = {}
        self.last_request_times: Dict[str, float] = {}
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads rate limits configuration from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                def_cfg = data.get("default", {})
                self.default_delay = float(def_cfg.get("delay_seconds", 1.0))

                sources = data.get("sources", {})
                if isinstance(sources, dict):
                    for sid, sinfo in sources.items():
                        if isinstance(sinfo, dict) and "delay_seconds" in sinfo:
                            self.source_limits[sid.lower().strip()] = float(sinfo["delay_seconds"])
            except Exception as e:
                logger.warning(f"Could not load rate_limits.yaml: {e}")

    def _extract_domain(self, url: str) -> str:
        """Extracts netloc domain string from URL."""
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lower() or url.lower()

    def wait(self, source_id: Optional[str] = None, url: Optional[str] = None) -> None:
        """
        Enforces rate limit delay for a target source or domain URL.

        Args:
            source_id: Optional target source identifier.
            url: Optional target request URL.
        """
        key = source_id.lower().strip() if source_id else self._extract_domain(url or "default")
        delay = self.source_limits.get(key, self.default_delay)

        last_time = self.last_request_times.get(key, 0.0)
        elapsed = time.time() - last_time

        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"RateLimiter throttling '{key}' for {sleep_time:.2f}s...")
            time.sleep(sleep_time)

        self.last_request_times[key] = time.time()
