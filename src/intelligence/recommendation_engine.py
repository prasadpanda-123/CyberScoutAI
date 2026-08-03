"""
Recommendation Engine for CyberScout AI.
"""

from typing import List, Optional

from src.models.opportunity import Opportunity


class RecommendationEngine:
    """
    Assigns rule-based recommendation reasons to surfaced opportunities.
    """

    def generate_recommendation_reason(self, opportunity: Opportunity, score: int) -> str:
        """
        Generates human-readable recommendation explanation reason.

        Args:
            opportunity: Target Opportunity instance.
            score: Final calculated overall score.

        Returns:
            Recommendation reason string.
        """
        reasons: List[str] = []

        if opportunity.paid is False and opportunity.certificate is True:
            reasons.append("Free Opportunity with Accredited Certificate")
        elif opportunity.paid is False:
            reasons.append("Free Opportunity")

        if opportunity.provider in ["CISA", "OWASP", "SANS Institute", "Google", "Microsoft", "AWS", "Cisco"]:
            reasons.append(f"Surfaced from Industry Recognized Provider ({opportunity.provider})")

        if opportunity.remote:
            reasons.append("Remote / Online Access")

        if not reasons:
            if score >= 80:
                return "Highly Ranked Opportunity Matching Cybersecurity Taxonomy"
            return "Surfaced Opportunity Matching Cybersecurity Category"

        return " | ".join(reasons)
