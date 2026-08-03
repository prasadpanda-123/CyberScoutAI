"""
Weighted Score Calculator for CyberScout AI.
"""

from typing import Any, Dict, Tuple

from src.models.opportunity import Opportunity
from src.intelligence.provider_engine import ProviderEngine
from src.intelligence.rule_engine import RuleEngine
from src.intelligence.weight_manager import WeightManager


class ScoreCalculator:
    """
    Computes overall score (0 to 100+) and detailed score breakdown dictionary.
    """

    def __init__(
        self,
        weight_manager: WeightManager,
        provider_engine: ProviderEngine,
        rule_engine: RuleEngine,
    ):
        self.weight_manager = weight_manager
        self.provider_engine = provider_engine
        self.rule_engine = rule_engine

    def calculate_score(self, opportunity: Opportunity) -> Tuple[int, Dict[str, Any]]:
        """
        Calculates weighted score and breakdown dictionary.

        Args:
            opportunity: Target Opportunity instance.

        Returns:
            Tuple of (overall_score_int, score_breakdown_dict).
        """
        score = 0
        breakdown: Dict[str, Any] = {}

        # 1. Base Quality Score
        base_quality = opportunity.score or 20
        score += base_quality
        breakdown["base_quality"] = base_quality

        # 2. Provider Bonus
        provider_bonus = self.provider_engine.get_provider_bonus(opportunity.provider)
        if provider_bonus > 0:
            score += provider_bonus
            breakdown["provider_bonus"] = provider_bonus

        # 3. Rule Evaluation Scores
        rules = self.rule_engine.evaluate_rules(opportunity)
        for rule_name, triggered in rules.items():
            if triggered:
                w = self.weight_manager.get_weight(rule_name)
                if w != 0:
                    score += w
                    breakdown[rule_name] = w

        final_score = max(0, score)
        return final_score, breakdown
