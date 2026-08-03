"""
Quality Metrics Engine for CyberScout AI.
"""

from typing import Any, Dict

from src.models.opportunity import Opportunity


class QualityEngine:
    """
    Computes quality metric score (0 to 100) based on metadata completeness.
    """

    def calculate_quality_score(self, opportunity: Opportunity) -> int:
        """
        Computes overall data completeness & quality score.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Quality score int (0–100).
        """
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
