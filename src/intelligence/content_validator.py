"""
Stage 1: Content & Syntax Validation Module for CyberScout AI.
"""

from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from src.core.logging import get_logger

logger = get_logger(__name__)


class ContentValidator:
    """
    Stage 1 Validator inspecting basic title length, description length, and URL syntax.
    """

    def __init__(self, min_title_len: int = 5, min_desc_len: int = 20):
        self.min_title_len = min_title_len
        self.min_desc_len = min_desc_len

    def validate(self, title: str, url: str, description: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates basic opportunity fields.

        Args:
            title: Opportunity title string.
            url: Opportunity URL string.
            description: Opportunity description text.

        Returns:
            Tuple of (is_valid, rejection_reason, detail_message)
        """
        if not title or not isinstance(title, str) or not title.strip():
            return False, "INVALID_CONTENT", "Title is empty or missing."

        clean_title = title.strip()
        if len(clean_title) < self.min_title_len:
            return False, "INVALID_CONTENT", f"Title length ({len(clean_title)}) under minimum threshold of {self.min_title_len} chars."

        if not url or not isinstance(url, str) or not url.strip():
            return False, "INVALID_CONTENT", "URL is missing."

        clean_url = url.strip()
        try:
            parsed = urlparse(clean_url)
            if not parsed.scheme or not parsed.netloc:
                return False, "INVALID_CONTENT", f"Invalid URL structure: '{clean_url}'."
        except Exception:
            return False, "INVALID_CONTENT", f"Malformed URL syntax: '{clean_url}'."

        clean_desc = (description or "").strip()
        if len(clean_desc) < self.min_desc_len:
            # Allow short descriptions if title or URL clearly indicates a known trusted security tool or API
            is_valid_short = any(term in clean_title.lower() for term in ["cve-", "advisory", "security", "patch", "ctf"])
            if not is_valid_short:
                return False, "INVALID_CONTENT", f"Description length ({len(clean_desc)}) under minimum threshold of {self.min_desc_len} chars."

        return True, None, None
