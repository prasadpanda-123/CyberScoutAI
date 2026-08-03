"""
Keyword Engine for CyberScout AI Search Intelligence Layer.

Loads keywords.yaml and synonyms.yaml, expands terms, handles synonym mapping,
categories, priorities, and keyword grouping.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml

from src.core.constants import CONFIG_DIR
from src.core.exceptions import IntelligenceError
from src.core.logging import get_logger

logger = get_logger(__name__)


class KeywordEngine:
    """
    Keyword loading, expansion, grouping, and priority management engine.
    """

    def __init__(
        self,
        keywords_file: Optional[Path] = None,
        synonyms_file: Optional[Path] = None,
    ):
        self.keywords_file = keywords_file or (CONFIG_DIR / "keywords.yaml")
        self.synonyms_file = synonyms_file or (CONFIG_DIR / "synonyms.yaml")

        self.categories: Dict[str, List[Dict[str, Any]]] = {}
        self.synonyms: Dict[str, List[str]] = {}

        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads keywords and synonyms from YAML files."""
        if self.keywords_file.exists():
            try:
                with open(self.keywords_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.categories = data.get("categories", data)
            except Exception as e:
                raise IntelligenceError(f"Failed to load keywords YAML '{self.keywords_file}': {e}", original_exception=e)

        if self.synonyms_file.exists():
            try:
                with open(self.synonyms_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    self.synonyms = data.get("synonyms", data)
            except Exception as e:
                raise IntelligenceError(f"Failed to load synonyms YAML '{self.synonyms_file}': {e}", original_exception=e)

        logger.info(f"KeywordEngine initialized with {len(self.categories)} categories and {len(self.synonyms)} synonym groups.")

    def get_all_keywords(self) -> List[str]:
        """Returns sorted list of all unique canonical keywords across categories."""
        terms: Set[str] = set()
        for domain, items in self.categories.items():
            if isinstance(items, dict) and "terms" in items:
                terms_list = items["terms"]
            elif isinstance(items, list):
                terms_list = items
            else:
                continue

            for item in terms_list:
                if isinstance(item, str):
                    terms.add(item.lower().strip())
                elif isinstance(item, dict) and "term" in item:
                    terms.add(item["term"].lower().strip())

        return sorted(list(terms))

    def get_keywords_by_category(self, category_name: str) -> List[str]:
        """Returns list of keywords belonging to a specific domain category, or all keywords if category is general/opportunity type."""
        if not category_name:
            return self.get_all_keywords()

        cat_clean = category_name.lower().strip()
        terms: List[str] = []

        if cat_clean in self.categories:
            items = self.categories[cat_clean]
            terms_list = items.get("terms", []) if isinstance(items, dict) else items
            for item in terms_list:
                t = item if isinstance(item, str) else item.get("term")
                if t:
                    terms.append(t.lower().strip())
            return terms

        # Fallback to all keywords if category_name is an opportunity category (e.g. 'internship') rather than domain category
        return self.get_all_keywords()

    def expand_keyword(self, keyword: str) -> List[str]:
        """
        Expands a keyword by appending its configured synonyms.

        Args:
            keyword: Base target keyword string.

        Returns:
            List of expanded keyword variations starting with the primary keyword.
        """
        keyword_clean = keyword.lower().strip()
        results: List[str] = [keyword_clean]

        if keyword_clean in self.synonyms:
            syn_list = self.synonyms[keyword_clean]
            for s in syn_list:
                s_clean = s.lower().strip()
                if s_clean not in results:
                    results.append(s_clean)

        return results

    def get_expanded_keywords(self, category_name: Optional[str] = None) -> List[str]:
        """
        Retrieves all expanded keywords (base terms + synonyms), optionally filtered by category.

        Args:
            category_name: Optional domain category filter.

        Returns:
            List of expanded unique keyword strings.
        """
        base_terms = (
            self.get_keywords_by_category(category_name)
            if category_name
            else self.get_all_keywords()
        )
        expanded_set: Set[str] = set()
        for term in base_terms:
            for variant in self.expand_keyword(term):
                expanded_set.add(variant)
        return sorted(list(expanded_set))
