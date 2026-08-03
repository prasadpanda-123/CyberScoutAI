"""
Search Template Engine for CyberScout AI.

Loads search_templates.yaml and renders keyword-template combinations.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.core.exceptions import IntelligenceError
from src.core.logging import get_logger
from src.intelligence.planner_models import SearchTemplate

logger = get_logger(__name__)


class SearchTemplateEngine:
    """
    Template loading, rendering, and management engine.
    """

    def __init__(self, templates_file: Optional[Path] = None):
        self.templates_file = templates_file or (CONFIG_DIR / "search_templates.yaml")
        self.templates_by_category: Dict[str, List[SearchTemplate]] = {}
        self.load_templates()

    def load_templates(self) -> None:
        """Loads search query templates from YAML file."""
        if not self.templates_file.exists():
            logger.warning(f"Search templates file not found at '{self.templates_file}'. Using defaults.")
            self._load_default_templates()
            return

        try:
            with open(self.templates_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            raw_templates = data.get("templates", data)
            if isinstance(raw_templates, dict):
                for category, patterns in raw_templates.items():
                    tmpl_list = []
                    if isinstance(patterns, list):
                        for pat in patterns:
                            if isinstance(pat, str):
                                tmpl_list.append(SearchTemplate(category=category, pattern=pat))
                            elif isinstance(pat, dict) and "pattern" in pat:
                                tmpl_list.append(
                                    SearchTemplate(
                                        category=category,
                                        pattern=pat["pattern"],
                                        weight=float(pat.get("weight", 1.0)),
                                    )
                                )
                    self.templates_by_category[category.lower().strip()] = tmpl_list
            logger.info(f"SearchTemplateEngine loaded templates across {len(self.templates_by_category)} categories.")
        except Exception as e:
            raise IntelligenceError(f"Failed to load search templates YAML: {e}", original_exception=e)

    def _load_default_templates(self) -> None:
        """Fallback default templates."""
        defaults = {
            "internship": ["{keyword} internship", "{keyword} internship remote"],
            "course": ["{keyword} free course", "{keyword} tutorial"],
            "certification": ["{keyword} certification", "{keyword} voucher"],
            "ctf": ["{keyword} ctf", "{keyword} capture the flag"],
        }
        for cat, patterns in defaults.items():
            self.templates_by_category[cat] = [
                SearchTemplate(category=cat, pattern=p) for p in patterns
            ]

    def get_templates_for_category(self, category: str) -> List[SearchTemplate]:
        """Returns list of SearchTemplate definitions for a given category."""
        return self.templates_by_category.get(category.lower().strip(), [])

    def render_queries(self, keyword: str, category: Optional[str] = None) -> List[str]:
        """
        Renders search query strings for a keyword across category templates.

        Args:
            keyword: Target keyword string.
            category: Optional category filter. If None, renders across all templates.

        Returns:
            List of unique rendered query strings.
        """
        rendered: List[str] = []
        target_categories = (
            [category.lower().strip()]
            if category and category.lower().strip() in self.templates_by_category
            else list(self.templates_by_category.keys())
        )

        for cat in target_categories:
            templates = self.templates_by_category.get(cat, [])
            for tmpl in templates:
                q = tmpl.render(keyword)
                if q not in rendered:
                    rendered.append(q)

        return rendered
