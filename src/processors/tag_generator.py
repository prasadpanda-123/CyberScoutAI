"""
Taxonomy Tag Generator for CyberScout AI.
"""

from pathlib import Path
from typing import List, Optional, Set
import yaml

from src.core.constants import CONFIG_DIR


class TagGenerator:
    """
    Generates taxonomy tags for an Opportunity based on text matching against taxonomy.yaml.
    """

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or (CONFIG_DIR / "taxonomy.yaml")
        self.taxonomy_tags: List[str] = []
        self.load_configuration()

    def load_configuration(self) -> None:
        """Loads tag taxonomy from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.taxonomy_tags = data.get("tags", [])
            except Exception:
                pass

    def generate_tags(self, title: str, description: str = "", existing_tags: Optional[List[str]] = None) -> List[str]:
        """
        Generates matched taxonomy tags for title and description.

        Args:
            title: Target title string.
            description: Target description text.
            existing_tags: List of existing tags.

        Returns:
            List of matching unique taxonomy tags.
        """
        text_lower = f"{title} {description}".lower()
        matched: Set[str] = set(existing_tags or [])

        for tag in self.taxonomy_tags:
            tag_clean = tag.lower().strip()
            if tag_clean and tag_clean in text_lower:
                matched.add(tag)

        return sorted(list(matched))
