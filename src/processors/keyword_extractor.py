"""
Keyword Extractor Processor for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

from src.core.constants import CONFIG_DIR
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor


class KeywordExtractorProcessor(BaseProcessor):
    """
    Extracts cybersecurity skills and technology keywords using synonym mappings.
    """

    def __init__(self, enabled: bool = True, config_file: Optional[Path] = None):
        super().__init__(enabled=enabled)
        self.config_file = config_file or (CONFIG_DIR / "skills.yaml")
        self.skill_map: Dict[str, str] = {}
        self.load_configuration()

    @property
    def processor_name(self) -> str:
        return "Keyword Extractor Processor"

    def load_configuration(self) -> None:
        """Loads skill synonym mappings from YAML configuration."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.skill_map = data.get("skills", {})
            except Exception:
                pass

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Extracts technology keywords and maps synonyms.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Opportunity with populated canonical tags.
        """
        if not self.enabled:
            return opportunity

        text_lower = f"{opportunity.title} {opportunity.description or ''}".lower()
        extracted: Set[str] = set(opportunity.tags or [])

        for synonym, canonical in self.skill_map.items():
            if f" {synonym.lower()} " in f" {text_lower} " or synonym.lower() in opportunity.tags:
                extracted.add(canonical)

        opportunity.tags = sorted(list(extracted))
        return opportunity
