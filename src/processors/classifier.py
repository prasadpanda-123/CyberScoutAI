"""
Rule-Based Category Classifier Processor for CyberScout AI.
"""

from pathlib import Path
from typing import Dict, List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.models.enums import OpportunityCategory
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor


class ClassifierProcessor(BaseProcessor):
    """
    Classifies Opportunity categories using rule-based keyword matching.
    """

    def __init__(self, enabled: bool = True, config_file: Optional[Path] = None):
        super().__init__(enabled=enabled)
        self.config_file = config_file or (CONFIG_DIR / "classification_rules.yaml")
        self.rules: Dict[str, List[str]] = {}
        self.load_configuration()

    @property
    def processor_name(self) -> str:
        return "Classifier Processor"

    def load_configuration(self) -> None:
        """Loads classification rules from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                rules_data = data.get("rules", {})
                for cat, cinfo in rules_data.items():
                    if isinstance(cinfo, dict) and "keywords" in cinfo:
                        self.rules[cat] = cinfo["keywords"]
            except Exception:
                pass

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Classifies category for Opportunity.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Opportunity instance with updated category.
        """
        if not self.enabled:
            return opportunity

        text_lower = f"{opportunity.title} {opportunity.description or ''}".lower()

        for cat, keywords in self.rules.items():
            if any(kw in text_lower for kw in keywords):
                if cat in [c.value for c in OpportunityCategory]:
                    opportunity.category = cat
                    break

        return opportunity
