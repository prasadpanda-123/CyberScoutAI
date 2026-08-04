"""
Master Production Data Intelligence Engine for CyberScout AI (Phase 12).
"""

from typing import Any, Dict, List, Optional
from src.core.logging import get_logger
from src.intelligence.production.content_verifier import ContentVerifier
from src.intelligence.production.duplicate_engine import SemanticDuplicateEngine
from src.intelligence.production.freshness_analyzer import FreshnessAnalyzer
from src.intelligence.production.historical_analyzer import HistoricalLifecycleAnalyzer
from src.intelligence.production.link_validator import LinkValidator
from src.intelligence.production.metrics import ProductionMetrics
from src.intelligence.production.provider_reliability import ProviderReliabilityEngine
from src.intelligence.production.trend_detector import TrendDetector
from src.models.opportunity import Opportunity

logger = get_logger(__name__)


class ProductionEngine:
    """
    Master Production Intelligence Engine integrating reliability, freshness, link validation,
    content verification, semantic deduplication, trend detection, and historical lifecycle tracking.
    """

    def __init__(
        self,
        reliability_engine: Optional[ProviderReliabilityEngine] = None,
        freshness_analyzer: Optional[FreshnessAnalyzer] = None,
        link_validator: Optional[LinkValidator] = None,
        content_verifier: Optional[ContentVerifier] = None,
        duplicate_engine: Optional[SemanticDuplicateEngine] = None,
        trend_detector: Optional[TrendDetector] = None,
        historical_analyzer: Optional[HistoricalLifecycleAnalyzer] = None,
    ):
        self.reliability = reliability_engine or ProviderReliabilityEngine()
        self.freshness = freshness_analyzer or FreshnessAnalyzer()
        self.link_validator = link_validator or LinkValidator()
        self.content_verifier = content_verifier or ContentVerifier()
        self.duplicate_engine = duplicate_engine or SemanticDuplicateEngine()
        self.trend_detector = trend_detector or TrendDetector()
        self.historical_analyzer = historical_analyzer or HistoricalLifecycleAnalyzer()
        self.metrics = ProductionMetrics()

    def evaluate_opportunity(self, opp: Opportunity) -> Opportunity:
        """
        Evaluates a single opportunity through Phase 12 Production Intelligence checks.
        """
        # 1. Provider Reliability Score
        provider_key = (opp.provider or opp.source_id or "generic_rss").lower()
        pstats = self.reliability.get_or_create_stats(provider_key)
        opp.provider_score = pstats.reliability_score

        # 2. Freshness & Decay
        f_score, days_old, days_rem, f_status, is_exp = self.freshness.analyze_freshness(
            published_date_str=opp.published_date,
            deadline_str=opp.deadline,
            discovered_date_str=opp.discovered_date,
        )
        opp.freshness_score = f_score
        opp.expired = 1 if is_exp else 0

        if is_exp:
            opp.archived = 1
            opp.status = "expired"

        # 3. Link Validation
        is_link_valid, link_code, link_msg = self.link_validator.validate_url(opp.url)
        opp.link_status = link_msg
        if not is_link_valid:
            opp.is_rejected = True
            opp.rejection_reason = f"DEAD_LINK_{link_code}"

        # 4. Content Verification
        if not opp.is_rejected:
            is_content_ver, ver_msg = self.content_verifier.verify_content(
                title=opp.title, description=opp.description
            )
            opp.verification_status = ver_msg
            if not is_content_ver:
                opp.is_rejected = True
                opp.rejection_reason = f"VERIFICATION_FAILED_{ver_msg}"
        else:
            opp.verification_status = "UNVERIFIED"

        self.metrics.record_item(
            is_accepted=not opp.is_rejected,
            confidence=opp.confidence_score,
            quality=opp.quality_score,
            freshness=opp.freshness_score,
            is_expired=bool(opp.expired),
            is_dead_link=not is_link_valid,
        )

        return opp

    def evaluate_batch(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """
        Evaluates a batch of opportunities through Production Intelligence and Deduplication.
        """
        # Step A: Individual evaluation
        evaluated = [self.evaluate_opportunity(opp) for opp in opportunities]

        # Step B: Semantic Deduplication
        active_items = [o for o in evaluated if not o.is_rejected]
        unique_items, merged_items = self.duplicate_engine.process_batch(active_items)

        for m in merged_items:
            self.metrics.record_item(is_accepted=False, is_duplicate=True)

        logger.info(
            f"ProductionEngine Evaluation Complete: {len(evaluated)} evaluated, "
            f"{len(unique_items)} unique active, {len(merged_items)} merged duplicates."
        )
        return evaluated
