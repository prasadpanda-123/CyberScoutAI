"""
Robots.txt Parser and Compliance Checker for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, Optional
import urllib.parse
import urllib.robotparser
import yaml

from src.core.constants import CONFIG_DIR
from src.core.logging import get_logger

logger = get_logger(__name__)


class RobotsChecker:
    """
    Checks robots.txt compliance before crawling HTML pages.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "robots.yaml")
        self.enabled = True
        self.strict_mode = False
        self.user_agent_name = "CyberScoutAI"
        self.parsers: Dict[str, urllib.robotparser.RobotFileParser] = {}
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads robots compliance settings from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.enabled = bool(data.get("enabled", True))
                self.strict_mode = bool(data.get("strict_mode", False))
                self.user_agent_name = data.get("default_user_agent_name", "CyberScoutAI")
            except Exception as e:
                logger.warning(f"Could not load robots.yaml: {e}")

    def is_allowed(self, url: str, robots_txt_content: Optional[str] = None) -> bool:
        """
        Checks if crawling target URL is allowed by robots.txt.

        Args:
            url: Target URL to crawl.
            robots_txt_content: Optional raw content of robots.txt.

        Returns:
            True if allowed, False if disallowed.
        """
        if not self.enabled:
            return True

        parsed = urllib.parse.urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self.parsers:
            rp = urllib.robotparser.RobotFileParser()
            if robots_txt_content:
                rp.parse(robots_txt_content.splitlines())
            else:
                rp.set_url(f"{domain}/robots.txt")
                try:
                    rp.read()
                except Exception:
                    # Default allow if robots.txt unreachable
                    rp.parse([])
            self.parsers[domain] = rp

        rp = self.parsers[domain]
        allowed = rp.can_fetch(self.user_agent_name, url)

        if not allowed:
            if self.strict_mode:
                logger.error(f"Robots.txt DISALLOW (strict mode): '{url}'")
            else:
                logger.warning(f"Robots.txt WARNING: Crawling '{url}' is disallowed by robots.txt rules.")

        return allowed
