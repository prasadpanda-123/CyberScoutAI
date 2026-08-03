"""
Confidence Engine for CyberScout AI.
"""

from typing import Any, Dict, Optional

from src.models.opportunity import Opportunity
from src.intelligence.quality_engine import QualityEngine


class ConfidenceEngine:
    """
    Calculates confidence score (0 to 100%) based on completeness, source, and provider reputation.
    """

    def __init__(self, quality_engine: Optional[QualityEngine] = None):
        self.quality_engine = quality_engine or QualityEngine()

    def calculate_confidence(self, opportunity: Opportunity) -> int:
        """
        Calculates confidence score percentage.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Confidence score int (0-100).
        """
        q_score = self.quality_engine.calculate_quality_score(opportunity)
        # Higher confidence for non-generic providers
        if opportunity.provider and opportunity.provider != "Unknown":
            q_score = min(100, q_score + 10)
        return q_score
