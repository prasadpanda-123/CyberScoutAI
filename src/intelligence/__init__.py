"""
Intelligence Package for CyberScout AI.

Note: Obsolete word-list search components (SearchPlanner, QueryBuilder, SearchTemplateEngine)
have been permanently removed in Phase B.1. Global opportunity discovery is now driven by
Tavily Search API via src.discovery.GlobalDiscoveryService.
"""

from src.intelligence.confidence_engine import ConfidenceEngine
from src.intelligence.deadline_engine import DeadlineEngine
from src.intelligence.duplicate_filter import DuplicateFilter
from src.intelligence.exceptions import IntelligenceError, RankingError, RuleError
from src.intelligence.interfaces import IRankingEngine
from src.intelligence.keyword_engine import KeywordEngine
from src.intelligence.metrics import RankingMetrics
from src.intelligence.planner_models import (
    SearchPlan,
    SearchResultMetadata,
    SearchTask,
)
from src.intelligence.priority_engine import PriorityEngine
from src.intelligence.provider_engine import ProviderEngine
from src.intelligence.quality_engine import QualityEngine
from src.intelligence.ranking_engine import RankingEngine
from src.intelligence.recommendation_engine import RecommendationEngine
from src.intelligence.rule_engine import RuleEngine
from src.intelligence.score_calculator import ScoreCalculator
from src.intelligence.source_registry import SourceRegistry
from src.intelligence.statistics import RankingStatistics
from src.intelligence.taxonomy import KeywordTaxonomy
from src.intelligence.weight_manager import WeightManager

__all__ = [
    # Taxonomy & Registry
    "KeywordEngine",
    "KeywordTaxonomy",
    "SourceRegistry",
    "SearchTask",
    "SearchPlan",
    "SearchResultMetadata",
    # Opportunity Intelligence & Ranking
    "RankingEngine",
    "RuleEngine",
    "ScoreCalculator",
    "WeightManager",
    "PriorityEngine",
    "RecommendationEngine",
    "DeadlineEngine",
    "ProviderEngine",
    "DuplicateFilter",
    "ConfidenceEngine",
    "QualityEngine",
    "RankingStatistics",
    "RankingMetrics",
    "IRankingEngine",
    "IntelligenceError",
    "RankingError",
    "RuleError",
]
