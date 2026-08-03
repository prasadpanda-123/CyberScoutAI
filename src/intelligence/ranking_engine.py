"""
Ranking Engine Orchestrator for CyberScout AI.
"""

import time
from typing import List, Optional

from src.core.logging import get_logger
from src.models.opportunity import Opportunity
from src.intelligence.confidence_engine import ConfidenceEngine
from src.intelligence.deadline_engine import DeadlineEngine
from src.intelligence.duplicate_filter import DuplicateFilter
from src.intelligence.interfaces import IRankingEngine
from src.intelligence.metrics import RankingMetrics
from src.intelligence.priority_engine import PriorityEngine
from src.intelligence.provider_engine import ProviderEngine
from src.intelligence.quality_engine import QualityEngine
from src.intelligence.recommendation_engine import RecommendationEngine
from src.intelligence.rule_engine import RuleEngine
from src.intelligence.score_calculator import ScoreCalculator
from src.intelligence.weight_manager import WeightManager

logger = get_logger(__name__)


class RankingEngine(IRankingEngine):
    """
    Master orchestrator for evaluating, scoring, prioritizing, and ranking opportunities.
    """

    def __init__(
        self,
        weight_manager: Optional[WeightManager] = None,
        provider_engine: Optional[ProviderEngine] = None,
        deadline_engine: Optional[DeadlineEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
        score_calculator: Optional[ScoreCalculator] = None,
        quality_engine: Optional[QualityEngine] = None,
        confidence_engine: Optional[ConfidenceEngine] = None,
        priority_engine: Optional[PriorityEngine] = None,
        recommendation_engine: Optional[RecommendationEngine] = None,
        duplicate_filter: Optional[DuplicateFilter] = None,
    ):
        self.weight_manager = weight_manager or WeightManager()
        self.provider_engine = provider_engine or ProviderEngine()
        self.deadline_engine = deadline_engine or DeadlineEngine()
        self.rule_engine = rule_engine or RuleEngine(
            weight_manager=self.weight_manager,
            provider_engine=self.provider_engine,
            deadline_engine=self.deadline_engine,
        )
        self.score_calculator = score_calculator or ScoreCalculator(
            weight_manager=self.weight_manager,
            provider_engine=self.provider_engine,
            rule_engine=self.rule_engine,
        )
        self.quality_engine = quality_engine or QualityEngine()
        self.confidence_engine = confidence_engine or ConfidenceEngine(quality_engine=self.quality_engine)
        self.priority_engine = priority_engine or PriorityEngine()
        self.recommendation_engine = recommendation_engine or RecommendationEngine()
        self.duplicate_filter = duplicate_filter or DuplicateFilter()
        self.metrics = RankingMetrics()

    def rank_opportunity(self, opportunity: Opportunity) -> Opportunity:
        """
        Ranks and scores an individual Opportunity.

        Args:
            opportunity: Input clean Opportunity instance.

        Returns:
            Ranked Opportunity instance with populated score, score_breakdown, and raw_data.
        """
        # 1. Calculate Score & Breakdown
        final_score, breakdown = self.score_calculator.calculate_score(opportunity)
        opportunity.score = final_score
        opportunity.score_breakdown = breakdown

        # 2. Assign Priority Level
        priority_level = self.priority_engine.assign_priority(final_score)

        # 3. Evaluate Deadline Status
        dl_status, days_left = self.deadline_engine.evaluate_deadline(opportunity.deadline)

        # 4. Compute Quality & Confidence
        quality_score = self.quality_engine.calculate_quality_score(opportunity)
        confidence_pct = self.confidence_engine.calculate_confidence(opportunity)

        # 5. Generate Recommendation Reason
        rec_reason = self.recommendation_engine.generate_recommendation_reason(opportunity, final_score)

        # Populate Metadata & raw_data fields for persistent DB storage
        if opportunity.raw_data is None:
            opportunity.raw_data = {}

        opportunity.raw_data["priority"] = priority_level
        opportunity.raw_data["confidence_score"] = confidence_pct
        opportunity.raw_data["quality_score"] = quality_score
        opportunity.raw_data["deadline_status"] = dl_status
        opportunity.raw_data["days_remaining"] = days_left
        opportunity.raw_data["recommendation_reason"] = rec_reason
        opportunity.raw_data["ranking_version"] = "v0.6.0"

        self.metrics.record_ranked(priority_level)
        return opportunity

    def rank_batch(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """
        Ranks, deduplicates, and sorts a batch of Opportunity instances by score descending.

        Args:
            opportunities: List of Opportunity objects.

        Returns:
            Sorted list of ranked unique Opportunity objects.
        """
        start_time = time.time()
        logger.info(f"RankingEngine starting ranking over {len(opportunities)} items...")

        ranked_items = [self.rank_opportunity(opp) for opp in opportunities]
        unique_items = self.duplicate_filter.filter_duplicates(ranked_items)
        unique_items.sort(key=lambda x: x.score, reverse=True)

        self.metrics.total_duration_seconds = time.time() - start_time
        logger.info(f"RankingEngine ranked {len(unique_items)} items in {self.metrics.total_duration_seconds:.2f}s.")
        return unique_items
