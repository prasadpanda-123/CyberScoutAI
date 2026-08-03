"""
Intelligence Package for CyberScout AI (Phase 2 Search Intelligence + Phase 5 Opportunity Intelligence).
"""

from src.intelligence.confidence_engine import ConfidenceEngine
from src.intelligence.deadline_engine import DeadlineEngine
from src.intelligence.duplicate_filter import DuplicateFilter
from src.intelligence.exceptions import IntelligenceError, RankingError, RuleError
from src.intelligence.interfaces import IRankingEngine
from src.intelligence.keyword_engine import KeywordEngine
from src.intelligence.metrics import RankingMetrics
from src.intelligence.planner_models import (
    SearchResultMetadata,
    SearchPlan,
    SearchTask,
    SearchTemplate,
    SearchValidationResult,
)
from src.intelligence.priority_engine import PriorityEngine
from src.intelligence.provider_engine import ProviderEngine
from src.intelligence.quality_engine import QualityEngine
from src.intelligence.query_builder import QueryBuilder
from src.intelligence.query_validator import QueryValidator
from src.intelligence.ranking_engine import RankingEngine
from src.intelligence.recommendation_engine import RecommendationEngine
from src.intelligence.rule_engine import RuleEngine
from src.intelligence.score_calculator import ScoreCalculator
from src.intelligence.search_planner import SearchPlanner
from src.intelligence.source_registry import SourceRegistry
from src.intelligence.statistics import RankingStatistics
from src.intelligence.template_engine import SearchTemplateEngine
from src.intelligence.weight_manager import WeightManager

__all__ = [
    # Phase 2 Search Intelligence
    "KeywordEngine",
    "SearchTemplateEngine",
    "SourceRegistry",
    "QueryBuilder",
    "QueryValidator",
    "SearchPlanner",
    "SearchTemplate",
    "SearchTask",
    "SearchPlan",
    "SearchResultMetadata",
    "SearchValidationResult",
    # Phase 5 Opportunity Intelligence
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
