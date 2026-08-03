"""
Keyword Taxonomy and Classification Intelligence for CyberScout AI.

Manages domain keyword taxonomy, synonym expansion, and text tagging.
"""

import re
from typing import Any, Dict, List, Set

from src.core.config import config
from src.core.logging import get_logger

logger = get_logger(__name__)


class KeywordTaxonomy:
    """
    Manages domain keywords, taxonomy matching, and tag classification.
    """

    def __init__(self, keywords_config: Dict[str, Any] | None = None):
        if keywords_config is None:
            keywords_config = config.get("keywords", {})
        self.keywords_config = keywords_config
        self._categories = self._parse_categories()

    def _parse_categories(self) -> Dict[str, Set[str]]:
        """Parses taxonomy categories and terms from config dict."""
        parsed: Dict[str, Set[str]] = {}
        if not isinstance(self.keywords_config, dict):
            return parsed

        categories = self.keywords_config.get("categories", self.keywords_config)
        if isinstance(categories, dict):
            for domain, terms in categories.items():
                term_set = set()
                if isinstance(terms, list):
                    for item in terms:
                        if isinstance(item, str):
                            term_set.add(item.lower().strip())
                        elif isinstance(item, dict) and "term" in item:
                            term_set.add(item["term"].lower().strip())
                parsed[domain] = term_set
        return parsed

    def match_tags(self, text: str) -> List[str]:
        """
        Scans input text and returns matching taxonomy domain tags and terms.

        Args:
            text: Title or description string.

        Returns:
            List of unique, lowercased matching tag strings.
        """
        if not text:
            return []

        text_lower = text.lower()
        matched_tags: Set[str] = set()

        for domain, terms in self._categories.items():
            for term in terms:
                # Use word boundary or substring match
                pattern = r"\b" + re.escape(term) + r"\b"
                if re.search(pattern, text_lower) or term in text_lower:
                    matched_tags.add(domain)
                    matched_tags.add(term)

        return sorted(list(matched_tags))
