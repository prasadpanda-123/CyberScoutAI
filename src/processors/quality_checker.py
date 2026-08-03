"""
Quality Checker Processor for CyberScout AI.
"""

from pathlib import Path
from typing import List, Optional
import yaml

from src.core.constants import CONFIG_DIR
from src.models.opportunity import Opportunity
from src.processors.base import BaseProcessor
from src.processors.exceptions import QualityError


class QualityCheckerProcessor(BaseProcessor):
    """
    Evaluates quality score (0-100) and filters spam or incomplete records.
    """

    def __init__(self, enabled: bool = True, config_file: Optional[Path] = None):
        super().__init__(enabled=enabled)
        self.config_file = config_file or (CONFIG_DIR / "quality_rules.yaml")
        self.min_quality_score = 40
        self.spam_keywords: List[str] = ["casino", "viagra", "crypto giveaway", "earn $1000 daily"]
        self.load_configuration()

    @property
    def processor_name(self) -> str:
        return "Quality Checker Processor"

    def load_configuration(self) -> None:
        """Loads quality rules from YAML file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                self.min_quality_score = int(data.get("min_quality_score", 40))
                self.spam_keywords = data.get("spam_keywords", self.spam_keywords)
            except Exception:
                pass

    def compute_quality_score(self, opportunity: Opportunity) -> int:
        """Computes quality score (0 to 100)."""
        score = 0
        if opportunity.url:
            score += 30
        if opportunity.title and len(opportunity.title) >= 5:
            score += 25
        if opportunity.description and len(opportunity.description) >= 10:
            score += 20
        if opportunity.provider and opportunity.provider != "Unknown":
            score += 15
        if opportunity.published_date or opportunity.deadline:
            score += 10
        return min(score, 100)

    def process(self, opportunity: Opportunity) -> Optional[Opportunity]:
        """
        Assesses quality score and rejects spam.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Quality-scored Opportunity, or None if rejected.
        """
        if not self.enabled:
            return opportunity

        text_lower = f"{opportunity.title} {opportunity.description or ''}".lower()
        if any(spam in text_lower for spam in self.spam_keywords):
            raise QualityError(f"Opportunity '{opportunity.title}' rejected as SPAM.")

        score = self.compute_quality_score(opportunity)
        opportunity.score = score

        if score < self.min_quality_score:
            return None

        return opportunity
